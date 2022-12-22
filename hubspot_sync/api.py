""" Generate Hubspot message bodies for various model objects"""
import logging
import re
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from hubspot.crm.objects import SimplePublicObject, SimplePublicObjectInput
from mitol.hubspot_api.api import (
    HubspotApi,
    HubspotAssociationType,
    HubspotObjectType,
    associate_objects_request,
    find_contact,
    find_deal,
    find_line_item,
    find_product,
    format_app_id,
    get_all_objects,
    get_line_items_for_deal,
    make_object_properties_message,
    transform_object_properties,
    upsert_object_request,
)
from mitol.hubspot_api.models import HubspotObject

from ecommerce.models import Line, Order, Product
from users.models import User

log = logging.getLogger(__name__)


def make_contact_sync_message(user_id: int) -> SimplePublicObjectInput:
    """
    Create the body of a sync message for a contact. This will flatten the contained LegalAddress and Profile
    serialized data into one larger serializable dict

    Args:
        user_id (int): User id

    Returns:
        SimplePublicObjectInput: input object for upserting User data to Hubspot
    """
    from users.serializers import UserSerializer

    contact_properties_map = {
        "email": "email",
        "name": "name",
        "first_name": "firstname",
        "last_name": "lastname",
        "country": "country",
    }

    user = User.objects.get(id=user_id)
    properties = UserSerializer(user).data
    properties.update(properties.pop("legal_address") or {})
    hubspot_props = transform_object_properties(properties, contact_properties_map)
    return make_object_properties_message(hubspot_props)


def make_deal_sync_message(order_id: int) -> SimplePublicObjectInput:
    """
    Create a hubspot sync input object for an Order.

    Args:
        order_id (int): Order id

    Returns:
        SimplePublicObjectInput: input object for upserting Order data to Hubspot
    """
    from hubspot_sync.serializers import OrderToDealSerializer

    order = Order.objects.get(id=order_id)
    properties = OrderToDealSerializer(order).data
    return make_object_properties_message(properties)


def make_line_item_sync_message(line_id: int) -> SimplePublicObjectInput:
    """
    Create a hubspot sync input object for a Line.

    Args:
        line_id (int): Line id

    Returns:
        SimplePublicObjectInput: input object for upserting Line data to Hubspot
    """
    from hubspot_sync.serializers import LineSerializer

    line = Line.objects.get(id=line_id)
    properties = LineSerializer(line).data
    return make_object_properties_message(properties)


def make_product_sync_message(product_id: int) -> SimplePublicObjectInput:
    """
    Create a hubspot sync input object for a product.

    Args:
        product_id (int): Product id

    Returns:
        SimplePublicObjectInput: input object for upserting Product data to Hubspot
    """
    from hubspot_sync.serializers import ProductSerializer

    product = Product.objects.get(id=product_id)
    properties = ProductSerializer(product).data
    return make_object_properties_message(properties)


def format_product_name(product: Product) -> str:
    """
    Get the product name as it should appear in Hubspot

    Args:
        product(Product): The product to return a name for

    Returns:
        str: The name of the Product as it should appear in Hubspot
    """
    product_obj = product.purchasable_object
    title_run_id = re.findall(r"\+R(\d+)$", product_obj.readable_id)
    title_suffix = f"Run {title_run_id[0]}" if title_run_id else product_obj.readable_id
    return f"{product_obj.title}: {title_suffix} [{format_app_id(product.id)}]"


def sync_contact_hubspot_ids_to_db():
    """
    Create HubspotObjects for all contacts in Hubspot

    Returns:
        bool: True if hubspot id matches found for all Users
    """
    contacts = get_all_objects(
        HubspotObjectType.CONTACTS.value, properties=["email", "hs_additional_emails"]
    )
    content_type = ContentType.objects.get_for_model(User)
    for contact in contacts:
        user = User.objects.filter(email__iexact=contact.properties["email"]).first()
        if not user and contact.properties["hs_additional_emails"]:
            alt_email_q = Q()
            for alt_email in contact.properties["hs_additional_emails"].split(";"):
                alt_email_q |= Q(email__iexact=alt_email)
            user = User.objects.filter(alt_email_q).first()
        if user:
            HubspotObject.objects.update_or_create(
                content_type=content_type,
                object_id=user.id,
                defaults={"hubspot_id": contact.id},
            )
    return (
        User.objects.count()
        == HubspotObject.objects.filter(content_type=content_type).count()
    )


def sync_product_hubspot_ids_to_db() -> bool:
    """
    Create HubspotObjects for products, return True if all products have hubspot ids

    Returns:
        bool: True if hubspot id matches found for all Products
    """
    content_type = ContentType.objects.get_for_model(Product)
    product_mapping = {}
    for product in Product.objects.all():
        product_mapping.setdefault(format_product_name(product), []).append(product.id)
    products = get_all_objects(HubspotObjectType.PRODUCTS.value)
    for product in products:
        matching_products = product_mapping.get(product.properties["name"])
        if not matching_products:
            continue
        if len(matching_products) > 1:
            # Narrow down by price
            matched_subquery = HubspotObject.objects.filter(
                content_type=content_type
            ).values_list("object_id", flat=True)
            matching_product = (
                Product.objects.exclude(id__in=matched_subquery)
                .filter(
                    id__in=matching_products,
                    price=Decimal(product.properties["price"]),
                )
                .order_by("-created_on")
                .values_list("id", flat=True)
                .first()
            )
        else:
            matching_product = matching_products[0]
        if matching_product:
            HubspotObject.objects.update_or_create(
                content_type=content_type,
                object_id=matching_product,
                defaults={"hubspot_id": product.id},
            )
    return (
        Product.objects.count()
        == HubspotObject.objects.filter(content_type=content_type).count()
    )


def sync_deal_hubspot_ids_to_db() -> bool:
    """
    Create Hubspot objects for orders and lines, return True if all orders
    (and optionally lines) have hubspot ids

    Returns:
        bool: True if matches found for all Orders and B2BOrders (and optionally their lines)
    """
    ct_order = ContentType.objects.get_for_model(Order)
    deals = get_all_objects(
        HubspotObjectType.DEALS.value, properties=["dealname", "amount"]
    )
    lines_synced = True
    for deal in deals:
        deal_name = deal.properties["dealname"]
        deal_price = Decimal(deal.properties["amount"] or "0.00")
        try:
            object_id = int(deal_name.split("-")[-1])
        except ValueError:
            # this isn't a deal that can be synced, ie "AMx Run 3 - SPIN MASTER"
            continue
        order = Order.objects.filter(id=object_id, total_price_paid=deal_price).first()
        content_type = ct_order
        if order:
            HubspotObject.objects.update_or_create(
                content_type=content_type,
                object_id=order.id,
                defaults={"hubspot_id": deal.id},
            )
            if not sync_deal_line_hubspot_ids_to_db(order, deal.id):
                lines_synced = False
    return (Order.objects.count()) == HubspotObject.objects.filter(
        content_type=ct_order
    ).count() and lines_synced


def sync_deal_line_hubspot_ids_to_db(order, hubspot_order_id) -> bool:
    """
    Create HubspotObjects for all of a deal's line items, return True if matches found for all lines

    Args:
        order(Order or B2BOrder): The order to sync Hubspot line items for
        hubspot_order_id(str): The Hubspot deal id

    Returns:
        bool: True if matches found for all the order lines

    """
    client = HubspotApi()
    line_items = get_line_items_for_deal(hubspot_order_id)
    order_line = order.lines.first()

    matches = 0
    expected_matches = order.lines.count()
    if len(line_items) == 1:
        HubspotObject.objects.update_or_create(
            content_type=ContentType.objects.get_for_model(order_line),
            object_id=order_line.id,
            defaults={"hubspot_id": line_items[0].id},
        )
        matches += 1
    else:  # Multiple lines, need to match by product and quantity
        for line in line_items:
            details = client.crm.line_items.basic_api.get_by_id(line.id)
            hs_product = HubspotObject.objects.filter(
                hubspot_id=details.properties["hs_product_id"],
                content_type=ContentType.objects.get_for_model(Product),
            ).first()
            if hs_product:
                product_id = hs_product.object_id
                matching_line = Line.objects.filter(
                    order=order,
                    product_version__object_id=product_id,
                    quantity=int(line.properties["quantity"]),
                ).first()
                if matching_line:
                    HubspotObject.objects.update_or_create(
                        content_type=ContentType.objects.get_for_model(Line),
                        object_id=matching_line.id,
                        defaults={"hubspot_id": line.id},
                    )
                    matches += 1
    return matches == expected_matches


def get_hubspot_id_for_object(
    obj: Order or Product or Line or User,
    raise_error: bool = False,
) -> str:
    """
    Get the hubspot id for an object, querying Hubspot if necessary

    Args:
        obj(object): The object (Order, B2BOrder, Product, Line, B2BLine or User) to get the id for
        raise_error(bool): raise an error if not found (default False)

    Returns:
        The hubspot id for the object if it has been previously synced to Hubspot.
        Raises a ValueError if no matching Hubspot object can be found.
    """
    from hubspot_sync.serializers import get_hubspot_serializer

    content_type = ContentType.objects.get_for_model(obj)
    hubspot_obj = HubspotObject.objects.filter(
        object_id=obj.id, content_type=content_type
    ).first()
    if hubspot_obj:
        return hubspot_obj.hubspot_id
    if isinstance(obj, User):
        try:
            hubspot_obj = find_contact(obj.email)
        except:
            log.exception(f"No User found w/ {obj.email}, is it active?")
    elif isinstance(obj, Order):
        serialized_deal = get_hubspot_serializer(obj).data
        hubspot_obj = find_deal(
            name=serialized_deal["dealname"],
            amount=serialized_deal["amount"],
            raise_count_error=raise_error,
        )
    elif isinstance(obj, Line):
        serialized_line = get_hubspot_serializer(obj).data
        order_id = get_hubspot_id_for_object(obj.order)
        if order_id:
            hubspot_obj = find_line_item(
                order_id,
                quantity=serialized_line["quantity"],
                hs_product_id=serialized_line["hs_product_id"],
                raise_count_error=raise_error,
            )
    elif isinstance(obj, Product):
        serialized_product = get_hubspot_serializer(obj).data
        hubspot_obj = find_product(
            serialized_product["name"],
            raise_count_error=raise_error,
        )
    if hubspot_obj and hubspot_obj.id:
        try:
            HubspotObject.objects.update_or_create(
                object_id=obj.id,
                content_type=content_type,
                defaults={"hubspot_id": hubspot_obj.id},
            )
        except:
            log.error(
                f"OBJ_ID: {obj.id}, ct: {content_type}, hubspot_id: {hubspot_obj.id}"
            )
            raise
        return hubspot_obj.id
    elif raise_error:
        raise ValueError(
            "Hubspot id could not be found for %s for id %d"
            % (content_type.name, obj.id)
        )


def sync_line_item_with_hubspot(line_id: int) -> SimplePublicObject:
    """
    Sync a Line with a hubspot line item

    Args:
        line_id(int): The Line id

    Returns:
        SimplePublicObject: The hubspot line_item object
    """
    line = Line.objects.get(id=line_id)
    body = make_line_item_sync_message(line_id)
    content_type = ContentType.objects.get_for_model(Line)

    # Check if a matching hubspot object has been or can be synced
    get_hubspot_id_for_object(line)

    # Create or update the line items
    result = upsert_object_request(
        content_type, HubspotObjectType.LINES.value, object_id=line_id, body=body
    )
    # Associate the parent deal with the line item
    associate_objects_request(
        HubspotObjectType.LINES.value,
        result.id,
        HubspotObjectType.DEALS.value,
        get_hubspot_id_for_object(line.order),
        HubspotAssociationType.LINE_DEAL.value,
    )
    return result


def sync_deal_with_hubspot(order_id: int) -> SimplePublicObject:
    """
    Sync an Order with a hubspot deal

    Args:
        order_id(int): The Order id

    Returns:
        SimplePublicObject: The hubspot deal object
    """
    order = Order.objects.get(id=order_id)
    body = make_deal_sync_message(order_id)
    content_type = ContentType.objects.get_for_model(Order)

    # Check if a matching hubspot object has been or can be synced
    get_hubspot_id_for_object(order)

    # Create or update the order aka deal
    result = upsert_object_request(
        content_type, HubspotObjectType.DEALS.value, object_id=order_id, body=body
    )
    # Create association between deal and contact
    associate_objects_request(
        HubspotObjectType.DEALS.value,
        result.id,
        HubspotObjectType.CONTACTS.value,
        get_hubspot_id_for_object(order.purchaser),
        HubspotAssociationType.DEAL_CONTACT.value,
    )

    for line in order.lines.all():
        sync_line_item_with_hubspot(line.id)
    return result


def sync_product_with_hubspot(product_id: int) -> SimplePublicObject:
    """
    Sync a Product with a hubspot product

    Args:
        product_id(int): The Product id

    Returns:
        SimplePublicObject: The hubspot product object
    """
    body = make_product_sync_message(product_id)
    content_type = ContentType.objects.get_for_model(Product)

    # Check if a matching hubspot object has been or can be synced
    get_hubspot_id_for_object(Product.objects.get(id=product_id))

    return upsert_object_request(
        content_type, HubspotObjectType.PRODUCTS.value, object_id=product_id, body=body
    )


def sync_contact_with_hubspot(user_id: int) -> SimplePublicObject:
    """
    Sync a user with a hubspot_sync contact

    Args:
        user_id(int): The User id

    Returns:
        SimplePublicObject: The hubspot contact object
    """
    body = make_contact_sync_message(user_id)
    content_type = ContentType.objects.get_for_model(User)

    return upsert_object_request(
        content_type, HubspotObjectType.CONTACTS.value, object_id=user_id, body=body
    )


MODEL_FUNCTION_MAPPING = {
    "user": make_contact_sync_message,
    "order": make_deal_sync_message,
    "line": make_line_item_sync_message,
    "product": make_product_sync_message,
}
