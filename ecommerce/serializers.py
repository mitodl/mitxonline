"""
MITxOnline ecommerce serializers
"""
from audioop import add
from decimal import Decimal

import pytz
from rest_framework import serializers

from cms.serializers import CoursePageSerializer
from courses.models import Course, CourseRun, ProgramRun
from ecommerce import models
from ecommerce.constants import (
    CYBERSOURCE_CARD_TYPES,
    DISCOUNT_TYPE_DOLLARS_OFF,
    DISCOUNT_TYPE_FIXED_PRICE,
    DISCOUNT_TYPE_PERCENT_OFF,
    DISCOUNT_TYPES,
    PAYMENT_TYPES,
    REDEMPTION_TYPE_ONE_TIME,
    REDEMPTION_TYPE_ONE_TIME_PER_USER,
    REDEMPTION_TYPE_UNLIMITED,
    REDEMPTION_TYPES,
    TRANSACTION_TYPE_REFUND,
)
from ecommerce.models import Basket, BasketItem, Order, Product
from flexiblepricing.api import determine_courseware_flexible_price_discount
from main.settings import TIME_ZONE
from users.serializers import ExtendedLegalAddressSerializer


class ProgramRunProductPurchasableObjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProgramRun
        fields = [
            "id",
            "run_tag",
            "start_date",
            "end_date",
        ]


class CoursePageObjectField(serializers.RelatedField):
    def to_representation(self, value):
        return CoursePageSerializer(instance=value).data


class CourseProductPurchasableObjectSerializer(serializers.ModelSerializer):
    page = CoursePageObjectField(read_only=True)

    class Meta:
        model = Course
        fields = ["id", "title", "page"]


class CourseRunProductPurchasableObjectSerializer(serializers.ModelSerializer):
    course = CourseProductPurchasableObjectSerializer(read_only=True)
    readable_id = serializers.CharField(source="text_id")

    class Meta:
        model = CourseRun
        fields = [
            "id",
            "title",
            "run_tag",
            "start_date",
            "end_date",
            "course",
            "readable_id",
            "enrollment_start",
            "enrollment_end",
            "course_number",
        ]


class ProductPurchasableObjectField(serializers.RelatedField):
    def to_representation(self, value):
        """Serialize the purchasable object using a serializer that matches the model type (either a Program Run or a Course Run)"""
        if isinstance(value, ProgramRun):
            return ProgramRunProductPurchasableObjectSerializer(instance=value).data
        elif isinstance(value, CourseRun):
            return CourseRunProductPurchasableObjectSerializer(instance=value).data
        raise Exception(
            "Unexpected to find type for Product.purchasable_object:", value.__class__
        )


class BaseProductSerializer(serializers.ModelSerializer):
    """Simple serializer for Product without related purchasable objects"""

    class Meta:
        fields = [
            "id",
            "price",
            "description",
            "is_active",
        ]
        model = models.Product


class ProductSerializer(BaseProductSerializer):
    purchasable_object = ProductPurchasableObjectField(read_only=True)

    class Meta:
        fields = BaseProductSerializer.Meta.fields + [
            "purchasable_object",
        ]
        model = models.Product


class ProductFlexibilePriceSerializer(BaseProductSerializer):
    product_flexible_price = serializers.SerializerMethodField()

    def get_product_flexible_price(self, instance):
        if not "request" in self.context:
            return None

        discount_record = determine_courseware_flexible_price_discount(
            instance, self.context["request"].user
        )
        return DiscountSerializer(discount_record, context=self.context).data

    class Meta:
        fields = BaseProductSerializer.Meta.fields + [
            "product_flexible_price",
        ]
        model = models.Product


class BasketItemSerializer(serializers.ModelSerializer):
    """BasketItem model serializer"""

    def perform_create(self, validated_data):
        basket = Basket.objects.get(user=validated_data["user"])
        # Product queryset returns active Products by default
        product = Product.objects.get(id=validated_data["product"])
        item, _ = BasketItem.objects.get_or_create(basket=basket, product=product)
        return item

    class Meta:
        model = models.BasketItem
        fields = [
            "basket",
            "product",
            "id",
        ]


class BasketSerializer(serializers.ModelSerializer):
    """Basket model serializer"""

    basket_items = serializers.SerializerMethodField()

    def get_basket_items(self, instance):
        """Get items in the basket"""
        return [
            BasketItemSerializer(instance=basket, context=self.context).data
            for basket in instance.basket_items.all()
        ]

    class Meta:
        fields = [
            "id",
            "user",
            "basket_items",
        ]
        model = models.Basket


class BasketDiscountSerializer(serializers.ModelSerializer):
    """BasketDiscount model serializer"""

    class Meta:
        model = models.BasketDiscount
        fields = ["redeemed_discount", "redeemed_basket"]
        depth = 1


class RedeemedDiscountSerializer(serializers.ModelSerializer):
    """DiscountRedemption model serializer"""

    class Meta:
        model = models.DiscountRedemption
        fields = ["redeemed_discount"]
        depth = 1


class BasketItemWithProductSerializer(serializers.ModelSerializer):
    product = serializers.SerializerMethodField()

    def get_product(self, instance):
        return ProductSerializer(instance=instance.product, context=self.context).data

    class Meta:
        model = models.BasketItem
        fields = ["basket", "product", "id"]
        depth = 1


class BasketWithProductSerializer(serializers.ModelSerializer):
    basket_items = serializers.SerializerMethodField()
    total_price = serializers.SerializerMethodField()
    discounted_price = serializers.SerializerMethodField()
    discounts = serializers.SerializerMethodField()

    def get_basket_items(self, instance):
        return [
            BasketItemWithProductSerializer(instance=basket, context=self.context).data
            for basket in instance.basket_items.all()
        ]

    def get_total_price(self, instance):
        return sum(
            basket_item.base_price for basket_item in instance.basket_items.all()
        )

    def get_discounted_price(self, instance):
        discounts = instance.discounts.all()

        if discounts.count() == 0:
            return self.get_total_price(instance)

        return sum(
            basket_item.discounted_price for basket_item in instance.basket_items.all()
        )

    def get_discounts(self, instance):
        """
        Exclude zero value discounts and return applicable discounts on the basket.
        """
        discounts = []
        for discount_record in instance.discounts.all():
            discount = discount_record.redeemed_discount
            if discount.amount == 0 and discount.discount_type in [
                DISCOUNT_TYPE_PERCENT_OFF,
                DISCOUNT_TYPE_DOLLARS_OFF,
            ]:
                continue

            discounts.append(
                BasketDiscountSerializer(discount_record, context=self.context).data
            )

        return discounts

    class Meta:
        fields = [
            "id",
            "user",
            "basket_items",
            "total_price",
            "discounted_price",
            "discounts",
        ]
        model = models.Basket


class LineSerializer(serializers.ModelSerializer):
    product = serializers.SerializerMethodField()

    def get_product(self, instance):
        product = models.Product.all_objects.get(
            pk=instance.product_version.field_dict["id"]
        )

        return ProductSerializer(instance=product).data

    class Meta:
        fields = [
            "quantity",
            "item_description",
            "content_type",
            "unit_price",
            "total_price",
            "id",
            "product",
        ]
        model = models.Line


class OrderSerializer(serializers.ModelSerializer):
    lines = serializers.SerializerMethodField()
    discounts = serializers.SerializerMethodField()
    refunds = serializers.SerializerMethodField()
    purchaser = serializers.SerializerMethodField()
    transactions = serializers.SerializerMethodField()
    street_address = serializers.SerializerMethodField()

    def get_lines(self, instance):
        """Get product information along with applied discounts"""
        return TransactionLineSerializer(instance.lines, many=True).data

    def get_discounts(self, instance):
        discounts = []
        for discount in instance.discounts.all():
            discounts.append(RedeemedDiscountSerializer(discount).data)
        return discounts

    def get_refunds(self, instance):
        refunds = []
        for transaction in (
            models.Transaction.objects.filter(order=instance)
            .filter(transaction_type=TRANSACTION_TYPE_REFUND)
            .all()
        ):
            refunds.append(
                {"amount": transaction.amount, "date": transaction.created_on}
            )

        return refunds

    def get_transactions(self, instance):
        """Get transaction information if it exists"""
        transaction = instance.transactions.order_by("-created_on").first()
        if transaction:
            data = {
                "card_number": None,
                "card_type": None,
                "name": None,
                "bill_to_email": None,
                "payment_method": None,
            }

            if "req_card_number" in transaction.data:
                data["card_number"] = transaction.data["req_card_number"]
            if (
                "req_card_type" in transaction.data
                and transaction.data["req_card_type"] in CYBERSOURCE_CARD_TYPES
            ):
                data["card_type"] = CYBERSOURCE_CARD_TYPES[
                    transaction.data["req_card_type"]
                ]
            if "req_payment_method" in transaction.data:
                data["payment_method"] = transaction.data["req_payment_method"]
            if "req_bill_to_email" in transaction.data:
                data["bill_to_email"] = transaction.data["req_bill_to_email"]
            if (
                "req_bill_to_forename" in transaction.data
                or "req_bill_to_surname" in transaction.data
            ):
                data[
                    "name"
                ] = f"{transaction.data.get('req_bill_to_forename')} {transaction.data.get('req_bill_to_surname')}"
            return data
        return None

    def get_street_address(self, instance):
        """Get the address information from the transaction"""
        transaction = instance.transactions.order_by("-created_on").first()
        if transaction:
            street_address = {
                "line": [],
                "postal_code": None,
                "state": None,
                "city": None,
                "country": None,
            }

            if "req_bill_to_address_line1" in transaction.data:
                street_address["line"].append(
                    transaction.data["req_bill_to_address_line1"]
                )
            if "req_bill_to_address_line2" in transaction.data:
                street_address["line"].append(
                    transaction.data["req_bill_to_address_line2"]
                )
            if "req_bill_to_address_postal_code" in transaction.data:
                street_address["postal_code"] = transaction.data[
                    "req_bill_to_address_postal_code"
                ]
            if "req_bill_to_address_state" in transaction.data:
                street_address["state"] = transaction.data["req_bill_to_address_state"]
            if "req_bill_to_address_city" in transaction.data:
                street_address["city"] = transaction.data["req_bill_to_address_city"]
            if "req_bill_to_address_country" in transaction.data:
                street_address["country"] = transaction.data[
                    "req_bill_to_address_country"
                ]

            return street_address
        return None

    def get_purchaser(self, instance):
        """Get the purchaser infrmation"""
        return ExtendedLegalAddressSerializer(instance.purchaser.legal_address).data

    class Meta:
        fields = [
            "id",
            "state",
            "purchaser",
            "total_price_paid",
            "lines",
            "discounts",
            "refunds",
            "reference_number",
            "created_on",
            "transactions",
            "street_address",
        ]
        model = models.Order


class OrderHistorySerializer(serializers.ModelSerializer):
    titles = serializers.SerializerMethodField()
    lines = LineSerializer(many=True)

    def get_titles(self, instance):
        titles = []

        for line in instance.lines.all():
            product = models.Product.all_objects.get(
                pk=line.product_version.field_dict["id"]
            )
            if product.content_type.model == "courserun":
                titles.append(product.purchasable_object.course.title)
            elif product.content_type.model == "programrun":
                titles.append(product.description)
            else:
                titles.append(f"No Title - {product.id}")

        return titles

    class Meta:
        fields = [
            "id",
            "state",
            "reference_number",
            "purchaser",
            "total_price_paid",
            "lines",
            "created_on",
            "titles",
        ]
        model = models.Order
        depth = 1


class DiscountSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Discount
        fields = [
            "id",
            "amount",
            "automatic",
            "discount_type",
            "redemption_type",
            "max_redemptions",
            "discount_code",
            "payment_type",
            "is_redeemed",
            "activation_date",
            "expiration_date",
        ]
        depth = 2


class DiscountRedemptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.DiscountRedemption
        fields = [
            "id",
            "redemption_date",
            "redeemed_by",
            "redeemed_discount",
            "redeemed_order",
        ]
        read_only_fields = [
            "redemption_date",
            "redeemed_by",
            "redeemed_discount",
            "redeemed_order",
        ]
        depth = 1


class DiscountProductSerializer(serializers.ModelSerializer):
    product = ProductSerializer()
    discount = DiscountSerializer()

    class Meta:
        model = models.DiscountProduct
        fields = [
            "id",
            "discount",
            "product",
        ]


class BulkDiscountSerializer(serializers.Serializer):
    """For validating bulk discount requests."""

    discount_type = serializers.ChoiceField(choices=DISCOUNT_TYPES)
    payment_type = serializers.ChoiceField(choices=PAYMENT_TYPES)
    amount = serializers.DecimalField(max_digits=9, decimal_places=2)
    one_time = serializers.BooleanField(default=False)
    one_time_per_user = serializers.BooleanField(default=False)
    activates = serializers.DateTimeField(
        required=False, default_timezone=pytz.timezone(TIME_ZONE)
    )
    expires = serializers.DateTimeField(
        required=False, default_timezone=pytz.timezone(TIME_ZONE)
    )
    count = serializers.IntegerField(required=False)
    prefix = serializers.CharField(max_length=63, required=False)


class UserDiscountSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.UserDiscount
        fields = [
            "id",
            "discount",
            "user",
        ]


class UserDiscountMetaSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.UserDiscount
        fields = [
            "id",
            "discount",
            "user",
        ]
        depth = 1


class TransactionDataSerializer(serializers.BaseSerializer):
    """
    Base serializer for transaction data - pulls just the data from a supplied
    Order object.
    """

    def to_representation(self, instance):
        if not isinstance(instance, Order):
            raise AttributeError()

        transaction = instance.transactions.order_by("-created_on").first()

        return transaction


class TransactionPurchaseSerializer(TransactionDataSerializer):
    """
    Serializes the purchase data out of the transaction.
    """

    def to_representation(self, instance):
        transaction = super().to_representation(instance).data

        data = {
            "card_number": None,
            "card_type": None,
            "name": None,
            "bill_to_email": None,
            "payment_method": None,
        }

        if "req_card_number" in transaction:
            data["card_number"] = transaction["req_card_number"]
        if (
            "req_card_type" in transaction
            and transaction["req_card_type"] in CYBERSOURCE_CARD_TYPES
        ):
            data["card_type"] = CYBERSOURCE_CARD_TYPES[transaction["req_card_type"]]
        if "req_payment_method" in transaction:
            data["payment_method"] = transaction["req_payment_method"]
        if "req_bill_to_email" in transaction:
            data["bill_to_email"] = transaction["req_bill_to_email"]
        if (
            "req_bill_to_forename" in transaction
            or "req_bill_to_surname" in transaction
        ):
            data[
                "name"
            ] = f"{transaction['req_bill_to_forename']} {transaction['req_bill_to_surname']}"

        return data


class TransactionPurchaserSerializer(TransactionDataSerializer):
    def to_representation(self, instance):
        """
        Get the purchaser information. Per discussion on this, the extended
        address data comes from the CyberSource payload.
        See https://github.com/mitodl/mitxonline/issues/532
        """
        transaction = super().to_representation(instance).data

        fields = {
            "first_name": instance.purchaser.legal_address.first_name,
            "last_name": instance.purchaser.legal_address.last_name,
            "country": instance.purchaser.legal_address.country,
            "email": instance.purchaser.email,
            "street_address": [],
            "street_address_1": None,
            "street_address_2": None,
            "street_address_3": None,
            "street_address_4": None,
            "street_address_5": None,
            "city": "",
            "state_or_territory": "",
            "postal_code": "",
            "company": "",
        }

        if "req_bill_to_email" in transaction:
            fields["email"] = transaction["req_bill_to_email"]

        if "req_bill_to_address_line1" in transaction:
            fields["street_address_1"] = transaction["req_bill_to_address_line1"]

        if "req_bill_to_address_line2" in transaction:
            fields["street_address_2"] = transaction["req_bill_to_address_line2"]

        if "req_bill_to_address_line3" in transaction:
            fields["street_address_3"] = transaction["req_bill_to_address_line3"]

        if "req_bill_to_address_city" in transaction:
            fields["city"] = transaction["req_bill_to_address_city"]

        if "req_bill_to_address_state" in transaction:
            fields["state_or_territory"] = transaction["req_bill_to_address_state"]

        if "req_bill_to_address_country" in transaction:
            fields["country"] = transaction["req_bill_to_address_country"]

        if "req_bill_to_address_postal_code" in transaction:
            fields["postal_code"] = transaction["req_bill_to_address_postal_code"]

        return fields

    def get_street_address(self, instance):
        street_address = [
            line
            for line in [
                self.street_address_1,
                self.street_address_2,
                self.street_address_3,
                self.street_address_4,
                self.street_address_5,
            ]
            if line
        ]


class TransactionOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ["id", "created_on", "reference_number"]
        read_only_fields = fields


class TransactionLineSerializer(serializers.BaseSerializer):
    def to_representation(self, instance):
        coupon_redemption = instance.order.discounts.first()
        discount = 0.0

        if coupon_redemption:
            discount = instance.product.price - instance.discounted_price

        total_paid = (instance.product.price - Decimal(discount)) * instance.quantity

        content_object = instance.product.purchasable_object
        (content_title, readable_id) = (None, None)

        if isinstance(content_object, ProgramRun):
            content_title = content_object.program.title
            readable_id = content_object.program.readable_id
        elif isinstance(content_object, CourseRun):
            readable_id = content_object.course.readable_id
            content_title = "{} {}".format(
                content_object.course_number, content_object.title
            )

        line = dict(
            quantity=instance.quantity,
            total_paid=str(total_paid),
            discount=str(discount),
            CEUs=None,
            content_title=content_title,
            readable_id=readable_id,
            price=str(instance.product.price),
            start_date=content_object.start_date,
            end_date=content_object.end_date,
        )

        return line


class OrderReceiptSerializer(serializers.ModelSerializer):
    """
    Serializer for extracting receipt info from an Order object
    This hews pretty closely to the data format in xPro but modified a bit
    for MITxOnline's data model.
    """

    lines = serializers.SerializerMethodField()
    purchaser = serializers.SerializerMethodField()
    coupon = serializers.SerializerMethodField()
    order = serializers.SerializerMethodField()
    receipt = serializers.SerializerMethodField()

    def get_receipt(self, instance):
        """
        Difference from xPRO: here we call it a transaction
        """
        return TransactionPurchaseSerializer(instance).data

    def get_lines(self, instance):
        """Get product information along with applied discounts"""
        return TransactionLineSerializer(instance.lines, many=True).data

    def get_order(self, instance):
        """Get order-specific information"""
        return TransactionOrderSerializer(instance).data

    def get_coupon(self, instance):
        """Get discount code from the discount redemption if available"""
        coupon_redemption = instance.discounts.first()
        if not coupon_redemption:
            return None
        return DiscountRedemptionSerializer(coupon_redemption).data

    def get_purchaser(self, instance):
        return TransactionPurchaserSerializer(instance).data

    class Meta:
        fields = ["purchaser", "lines", "coupon", "order", "receipt"]
        model = models.Order
