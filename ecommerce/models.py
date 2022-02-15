from django.conf import settings
from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django_fsm import FSMField, transition
from mitol.common.models import TimestampedModel
import reversion
from ecommerce.constants import (
    DISCOUNT_TYPES,
    REDEMPTION_TYPES,
    REFERENCE_NUMBER_PREFIX,
)
from users.models import User

User = get_user_model()


def valid_purchasable_objects_list():
    return models.Q(app_label="courses", model="courserun") | models.Q(
        app_label="courses", model="programrun"
    )


@reversion.register(exclude=("created_on", "updated_on"))
class Product(TimestampedModel):
    """
    Representation of a purchasable product. There is a GenericForeignKey to a
    Course Run or Program Run.
    """

    valid_purchasable_objects = valid_purchasable_objects_list()
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to=valid_purchasable_objects,
    )
    object_id = models.PositiveIntegerField()
    purchasable_object = GenericForeignKey("content_type", "object_id")

    price = models.DecimalField(max_digits=7, decimal_places=2, help_text="")
    description = models.TextField()
    is_active = models.BooleanField(
        default=True,
        null=False,
        help_text="Controls visibility of the product in the app.",
    )

    def __str__(self):
        return f"{self.description} {self.price}"


class Basket(TimestampedModel):
    """Represents a User's basket."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="basket")


class BasketItem(TimestampedModel):
    """Represents one or more products in a user's basket."""

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="basket_item"
    )
    basket = models.ForeignKey(
        Basket, on_delete=models.CASCADE, related_name="basket_items"
    )
    quantity = models.PositiveIntegerField(default=1)


class Discount(TimestampedModel):
    """Discount model"""

    amount = models.DecimalField(
        decimal_places=5,
        max_digits=20,
    )
    automatic = models.BooleanField(default=False)
    discount_type = models.CharField(choices=DISCOUNT_TYPES, max_length=30)
    redemption_type = models.CharField(choices=REDEMPTION_TYPES, max_length=30)
    max_redemptions = models.PositiveIntegerField(null=True, default=0)

    def __str__(self):
        return f"{self.amount} {self.discount_type} {self.redemption_type}"


class UserDiscount(TimestampedModel):
    """pre-assignment for a discount to a user"""

    discount = models.ForeignKey(
        Discount, on_delete=models.CASCADE, related_name="user_discount_discount"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="user_discount_user",
    )

    def __str__(self):
        return f"{self.discount} {self.user}"


class Order(TimestampedModel):
    """An order containing information for a purchase."""

    class STATE:
        PENDING = "pending"
        FULFILLED = "fulfilled"
        CANCELED = "canceled"
        REFUNDED = "refunded"

        @classmethod
        def choices(cls):
            return (
                (cls.PENDING, "Pending", "PendingOrder"),
                (cls.FULFILLED, "Fulfilled", "FulfilledOrder"),
                (cls.CANCELED, "Canceled", "CanceledOrder"),
                (cls.REFUNDED, "Refunded", "RefundedOrder"),
            )

    state = FSMField(default=STATE.PENDING, state_choices=STATE.choices())
    purchaser = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="orders",
    )
    total_price_paid = models.DecimalField(
        decimal_places=5,
        max_digits=20,
    )

    @transition(field=state, source=STATE.PENDING, target=STATE.FULFILLED)
    def fulfill(self):
        """Fulfill this order"""
        raise NotImplementedError()

    @transition(field=state, source=STATE.PENDING, target=STATE.CANCELED)
    def cancel(self):
        """Cancel this order"""
        raise NotImplementedError()

    @transition(field=state, source=STATE.FULFILLED, target=STATE.REFUNDED)
    def refund(self):
        """Issue a refund"""
        raise NotImplementedError()

    @property
    def reference_number(self):
        return f"{REFERENCE_NUMBER_PREFIX}{settings.ENVIRONMENT}-{self.id}"

    def __str__(self):
        return f"{self.state.capitalize()} Order for {self.purchaser.name} ({self.purchaser.email})"

    @staticmethod
    def decode_reference_number(refno):
        return refno.replace(f"{REFERENCE_NUMBER_PREFIX}{settings.ENVIRONMENT}-", "")


class PendingOrder(Order):
    """An order that is pending payment"""

    def fulfill(self):
        """Fulfill this order"""
        pass

    def cancel(self):
        """Cancel this order"""
        pass

    class Meta:
        proxy = True


class FulfilledOrder(Order):
    """An order that has a fulfilled payment"""

    def refund(self):
        """Issue a refund"""
        pass

    class Meta:
        proxy = True


class CanceledOrder(Order):
    """
    An order that is canceled.

    The state of this can't be altered further.
    """

    class Meta:
        proxy = True


class RefundedOrder(Order):
    """
    An order that is refunded.

    The state of this can't be altered further.
    """

    class Meta:
        proxy = True


class Line(TimestampedModel):
    """A line in an Order."""

    def _order_line_product_versions():
        """Returns a Q object filtering to Versions for Products"""
        return models.Q()

    order = models.ForeignKey(
        "ecommerce.Order",
        on_delete=models.CASCADE,
        related_name="lines",
    )
    product_version = models.ForeignKey(
        "reversion.Version",
        limit_choices_to=_order_line_product_versions,
        on_delete=models.CASCADE,
    )
    quantity = models.PositiveIntegerField()

    @property
    def unit_price(self):
        """Return the price of the product"""
        return self.product_version.field_dict["price"]

    @property
    def total_price(self):
        """Return the price of the product"""
        return self.unit_price * self.quantity

    def __str__(self):
        return f"{self.product_version}"


class Transaction(TimestampedModel):
    """A transaction on an order, generally a payment but can also cover refunds"""

    order = models.ForeignKey(
        "ecommerce.Order", on_delete=models.CASCADE, related_name="transactions"
    )
    amount = models.DecimalField(
        decimal_places=5,
        max_digits=20,
    )
    data = models.JSONField()


class BasketDiscount(TimestampedModel):
    """
    This is a mirror of DiscountRedemption, but is designed to attach the
    redemption to a Basket rather than an Order, allowing discount codes to be
    used as long as a customer has a basket at all. These also need to be
    ephemeral, so we don't clog up the DiscountRedemption model with FKs to
    removed objects.
    """

    redemption_date = models.DateTimeField()
    redeemed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="basketdiscount_user",
    )
    redeemed_discount = models.ForeignKey(
        Discount, on_delete=models.CASCADE, related_name="basketdiscount_discount"
    )
    redeemed_basket = models.ForeignKey(
        Basket, on_delete=models.CASCADE, related_name="basketdiscount_basket"
    )

    def __str__(self):
        return f"{self.redemption_date}: {self.redeemed_discount}, {self.redeemed_by}"


class DiscountRedemption(TimestampedModel):
    """
    Tracks when discounts were redeemed, for discounts that aren't unlimited use
    """

    redemption_date = models.DateTimeField()
    redeemed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="redeemed_by_user",
    )
    redeemed_discount = models.ForeignKey(
        Discount, on_delete=models.CASCADE, related_name="redeemed_discount"
    )
    redeemed_order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="redeemed_order"
    )

    def __str__(self):
        return f"{self.redemption_date}: {self.redeemed_discount}, {self.redeemed_by}"
