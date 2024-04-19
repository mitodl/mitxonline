"""Serializers for HubSpot"""

from decimal import Decimal

from django.conf import settings
from mitol.hubspot_api.api import format_app_id
from rest_framework import serializers

from courses.models import CourseRunEnrollment
from ecommerce import models
from ecommerce.constants import DISCOUNT_TYPE_DOLLARS_OFF, DISCOUNT_TYPE_PERCENT_OFF
from ecommerce.discounts import resolve_product_version
from ecommerce.models import Product
from hubspot_sync.api import format_product_name, get_hubspot_id_for_object
from main.utils import format_decimal

"""
Map order state to hubspot ids for pipeline stages
These IDs are specific to the prod & sandbox accounts for mitxonline
48288379: Checkout Abandoned
48288388: Checkout Pending
48288389: Checkout Completed
48288390: Processed
"""
ORDER_STATUS_MAPPING = {
    models.Order.STATE.FULFILLED: "48288390",
    models.Order.STATE.PENDING: "48288388",
    models.Order.STATE.CANCELED: "48288379",
    models.Order.STATE.DECLINED: "48288389",
    models.Order.STATE.ERRORED: "48288389",
    models.Order.STATE.REFUNDED: "48288389",
    models.Order.STATE.PARTIALLY_REFUNDED: "48288389",
    models.Order.STATE.REVIEW: "48288390",
}


class LineSerializer(serializers.ModelSerializer):
    """Line Serializer for Hubspot"""

    unique_app_id = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    hs_product_id = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    product_id = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    enrollment_mode = serializers.SerializerMethodField()
    change_status = serializers.SerializerMethodField()

    _product = None
    _enrollment = None

    def _get_product(self, instance):
        """Retrieve the line product just once"""
        if not self._product:
            version = instance.product_version
            product = Product.all_objects.filter(id=version.object_id).first()
            if product:
                self._product = resolve_product_version(
                    product, product_version=version
                )
            else:
                self._product = version.object
        return self._product

    def _get_enrollment(self, instance):
        """Returns the CourseRunEnrollment associated with the Order, if one exists, else None"""
        self._enrollment = CourseRunEnrollment.all_objects.filter(
            run=instance.purchased_object, user=instance.order.purchaser
        ).first()
        return self._enrollment

    def get_enrollment_mode(self, instance):
        """Returns the CourseRunEnrollment's mode associated with the Order, if a CourseRunEnrollment exists, else None"""
        enrollment = self._get_enrollment(instance)
        return enrollment.enrollment_mode if enrollment is not None else None

    def get_change_status(self, instance):
        """Returns the CourseRunEnrollment's change_status associated with the Order, if a CourseRunEnrollment exists, else None"""
        enrollment = self._get_enrollment(instance)
        return enrollment.change_status if enrollment is not None else None

    def get_unique_app_id(self, instance):
        """Get the app_id for the object"""
        return format_app_id(instance.id)

    def get_name(self, instance):
        """Get the product version name"""
        if instance.product_version:
            return format_product_name(self._get_product(instance))
        return ""

    def get_hs_product_id(self, instance):
        """Return the hubspot id for the product"""
        if not instance.product_version:
            return None
        return get_hubspot_id_for_object(self._get_product(instance))

    def get_status(self, instance):
        """Get status of the associated Order"""
        return instance.order.state

    def get_product_id(self, instance):
        """Return the product version text_id"""
        product = self._get_product(instance)
        if product:  # noqa: RET503
            return product.purchasable_object.readable_id

    def get_price(self, instance):
        """Get the product version price"""
        product = self._get_product(instance)
        if product:  # noqa: RET503
            return format_decimal(product.price)

    class Meta:
        fields = (
            "unique_app_id",
            "name",
            "hs_product_id",
            "quantity",
            "status",
            "product_id",
            "price",
            "enrollment_mode",
            "change_status",
        )
        model = models.Line


class OrderToDealSerializer(serializers.ModelSerializer):
    """Order/Deal Serializer for Hubspot"""

    unique_app_id = serializers.SerializerMethodField()
    dealname = serializers.SerializerMethodField()
    dealstage = serializers.SerializerMethodField()
    closedate = serializers.SerializerMethodField(allow_null=True)
    amount = serializers.SerializerMethodField()
    discount_amount = serializers.SerializerMethodField()
    discount_percent = serializers.SerializerMethodField()
    discount_type = serializers.SerializerMethodField()
    coupon_code = serializers.SerializerMethodField(allow_null=True)
    pipeline = serializers.ReadOnlyField(default=settings.HUBSPOT_PIPELINE_ID)
    status = serializers.ReadOnlyField(source="state")

    _discount_checked = False
    _discount = None
    _product = None

    def _get_product(self, instance):
        """Retrieve the line product just once"""
        if not self._product:
            version = instance.lines.first().product_version
            product = Product.objects.filter(id=version.object_id).first()
            if product:
                self._product = resolve_product_version(
                    product, product_version=version
                )
            else:
                self._product = version.object
        return self._product

    def _get_discount(self, instance):
        """Return the order discount"""
        if self._discount is None and not self._discount_checked:
            redemption = instance.discounts.first()
            self._discount_checked = True
            if redemption:
                self._discount = instance.discounts.first().redeemed_discount
        return self._discount

    def get_unique_app_id(self, instance):
        """Get the app_id for the object"""
        return format_app_id(instance.id)

    def get_dealname(self, instance):
        """Return the order/deal name"""
        return f"MITXONLINE-ORDER-{instance.id}"

    def get_dealstage(self, instance):
        """Return the state mapped to the hubspot equivalent"""
        return ORDER_STATUS_MAPPING[instance.state]

    def get_closedate(self, instance):
        """Return the updated_on date (as a timestamp in milliseconds) if fulfilled"""
        if instance.state == models.Order.STATE.FULFILLED:  # noqa: RET503
            return int(instance.updated_on.timestamp() * 1000)

    def get_discount_type(self, instance):
        """Get the discount type of the applied coupon"""
        discount = self._get_discount(instance)
        if discount:  # noqa: RET503
            return discount.discount_type

    def get_amount(self, instance):
        """Get the amount paid after discount"""
        return format_decimal(instance.total_price_paid)

    def get_discount_amount(self, instance):
        """Get the discount amount if any"""
        discount = self._get_discount(instance)
        if not discount:
            return "0.00"
        product_price = self._get_product(instance).price
        if discount.discount_type == DISCOUNT_TYPE_PERCENT_OFF:
            discount_amount = Decimal(product_price * (discount.amount / 100))
        elif discount.discount_type == DISCOUNT_TYPE_DOLLARS_OFF:
            discount_amount = discount.amount
        else:
            discount_amount = Decimal(product_price - discount.amount)
        return format_decimal(discount_amount)

    def get_discount_percent(self, instance):
        """Get the discount percentage if any"""
        discount = self._get_discount(instance)
        if not discount:
            return "0"
        product_price = self._get_product(instance).price
        if discount.discount_type == DISCOUNT_TYPE_PERCENT_OFF:
            discount_percent = discount.amount
        elif discount.discount_type == DISCOUNT_TYPE_DOLLARS_OFF:
            discount_percent = Decimal(discount.amount / product_price) * 100
        else:
            discount_percent = Decimal(
                ((product_price - discount.amount) / product_price) * 100
            )
        return format_decimal(discount_percent)

    def get_coupon_code(self, instance):
        """Get the coupon code used for the order if any"""
        discount = self._get_discount(instance)
        if discount:  # noqa: RET503
            return discount.discount_code

    class Meta:
        fields = (
            "unique_app_id",
            "dealname",
            "amount",
            "dealstage",
            "status",
            "discount_amount",
            "discount_percent",
            "discount_type",
            "closedate",
            "coupon_code",
            "pipeline",
        )
        model = models.Order


class ProductSerializer(serializers.ModelSerializer):
    """Product Serializer for Hubspot"""

    unique_app_id = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()

    def get_unique_app_id(self, instance):
        """Get the app_id for the object"""
        return format_app_id(instance.id)

    def get_name(self, instance):
        """Return the product title and Courserun number or ProductVersion text_id"""
        return format_product_name(instance)

    def get_price(self, instance):
        """Return the latest product version price"""
        if instance.price:
            return format_decimal(instance.price)
        return "0.00"

    class Meta:
        fields = ["unique_app_id", "name", "price", "description"]
        read_only_fields = fields
        model = models.Product


def get_hubspot_serializer(obj: object) -> serializers.ModelSerializer:
    """Get the appropriate serializer for an object"""
    if isinstance(obj, models.Order):
        serializer_class = OrderToDealSerializer
    elif isinstance(obj, models.Line):
        serializer_class = LineSerializer
    elif isinstance(obj, models.Product):
        serializer_class = ProductSerializer
    else:
        raise NotImplementedError("Not a supported class")  # noqa: EM101
    return serializer_class(obj)
