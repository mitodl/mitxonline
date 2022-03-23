from django.db.models import Prefetch
from django.utils.functional import cached_property
from django.conf import settings
from django.db import models, transaction
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from courses.models import CourseRun, CourseRunEnrollment
from courses.constants import ENROLL_CHANGE_STATUS_REFUNDED
from courses.models import CourseRun
from django_fsm import FSMField, transition
from mitol.common.models import TimestampedModel
from openedx.constants import EDX_ENROLLMENT_VERIFIED_MODE
import reversion
from reversion.models import Version
from ecommerce.constants import (
    DISCOUNT_TYPES,
    REDEMPTION_TYPES,
    TRANSACTION_TYPE_PAYMENT,
    TRANSACTION_TYPES,
    REFERENCE_NUMBER_PREFIX,
    REDEMPTION_TYPE_ONE_TIME,
    REDEMPTION_TYPE_ONE_TIME_PER_USER,
    REDEMPTION_TYPE_UNLIMITED,
)
from users.models import User
from decimal import Decimal
from courses.api import deactivate_run_enrollment

from mitol.common.utils.datetime import now_in_utc

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

    def has_user_blocked_products(self, user):
        """Return true if any of the courses in the basket block user's country"""
        basket_items = self.basket_items.prefetch_related("product")
        return any(
            [
                item.product.purchasable_object.course.is_country_blocked(user)
                for item in basket_items
            ]
        )

    def compare_to_order(self, order):
        """
        Compares this basket with the specified order. An order is considered
        equal to the basket if it meets these criteria:
        - Users match
        - Products match on each line
        - Discounts match
        """
        if self.user != order.purchaser:
            return False

        all_items_found = self.basket_items.count() == order.lines.count()
        all_discounts_found = self.discounts.count() == order.discounts.count()

        if all_items_found:
            for basket_item in self.basket_items.all():
                for order_item in order.lines.all():
                    if order_item.product != basket_item.product:
                        all_items_found = False

        if all_discounts_found:
            for basket_discount in self.discounts.all():
                for order_discount in order.discounts.all():
                    if (
                        basket_discount.redeemed_discount
                        != order_discount.redeemed_discount
                    ):
                        all_discounts_found = False

        if all_items_found is False or all_discounts_found is False:
            return False

        return True


class BasketItem(TimestampedModel):
    """Represents one or more products in a user's basket."""

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="basket_item"
    )
    basket = models.ForeignKey(
        Basket, on_delete=models.CASCADE, related_name="basket_items"
    )
    quantity = models.PositiveIntegerField(default=1)

    @cached_property
    def discounted_price(self):
        """Return the price of the product with discounts"""
        from ecommerce.discounts import DiscountType

        discounts = [
            discount_redemption.redeemed_discount
            for discount_redemption in self.basket.discounts.all()
        ]

        return (
            DiscountType.get_discounted_price(
                discounts,
                self.product,
            ).quantize(Decimal("0.01"))
            * self.quantity
        )

    @cached_property
    def base_price(self):
        """Returns the total price of the basket item without discounts."""
        return self.product.price * self.quantity


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
    discount_code = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.amount} {self.discount_type} {self.redemption_type} - {self.discount_code}"

    def check_validity(self, user: User):
        """
        Enforces the redemption rules for a given discount.

        Args:
            - user (User): The user requesting the discount.
        Returns:
            - boolean
        """
        if (
            self.redemption_type == REDEMPTION_TYPE_ONE_TIME
            and DiscountRedemption.objects.filter(redeemed_discount=self).count() > 0
        ):
            return False

        if (
            self.redemption_type == REDEMPTION_TYPE_ONE_TIME_PER_USER
            and DiscountRedemption.objects.filter(redeemed_discount=self)
            .filter(redeemed_by=user)
            .count()
            > 0
        ):
            return False

        if (
            self.max_redemptions > 0
            and DiscountRedemption.objects.filter(redeemed_discount=self).count()
            >= self.max_redemptions
        ):
            return False

        return True


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
        DECLINED = "declined"
        ERRORED = "errored"
        REFUNDED = "refunded"
        REVIEW = "review"

        @classmethod
        def choices(cls):
            return (
                (cls.PENDING, "Pending", "PendingOrder"),
                (cls.FULFILLED, "Fulfilled", "FulfilledOrder"),
                (cls.CANCELED, "Canceled", "CanceledOrder"),
                (cls.REFUNDED, "Refunded", "RefundedOrder"),
                (cls.DECLINED, "Declined", "DeclinedOrder"),
                (cls.ERRORED, "Errored", "ErroredOrder"),
                (cls.REVIEW, "Review", "ReviewOrder"),
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
    # Flag to determine if the order is in review status - if it is, then
    # we need to not step on the basket that may or may not exist when it is
    # accepted
    @property
    def is_review(self):
        return self.state == Order.STATE.REVIEW

    def fulfill(self, payment_data):
        """Fulfill this order"""
        raise NotImplementedError()

    def cancel(self):
        """Cancel this order"""
        raise NotImplementedError()

    def decline(self):
        """Decline this order"""
        raise NotImplementedError()

    def review(self):
        """Place order in review"""
        raise NotImplementedError()

    def errored(self):
        """Error this order"""
        raise NotImplementedError()

    def refund(self, amount, reason, unenroll_learner):
        """Issue a refund"""
        raise NotImplementedError()

    @property
    def reference_number(self):
        return f"{REFERENCE_NUMBER_PREFIX}{settings.ENVIRONMENT}-{self.id}"

    @property
    def purchased_runs(self):
        """Return a list of purchased CourseRuns"""

        # TODO: handle programs
        return [
            line.purchased_object
            for line in self.lines.all()
            if isinstance(line.purchased_object, CourseRun)
        ]

    def __str__(self):
        return f"{self.state.capitalize()} Order for {self.purchaser.name} ({self.purchaser.email})"

    @staticmethod
    def decode_reference_number(refno):
        return refno.replace(f"{REFERENCE_NUMBER_PREFIX}{settings.ENVIRONMENT}-", "")


class PendingOrder(Order):
    """An order that is pending payment"""

    @classmethod
    @transaction.atomic()
    def create_from_basket(cls, basket: Basket):
        """
        Creates a new pending order from a basket

        Args:
            basket (Basket):  the user's basket to create an order for

        Returns:
            PendingOrder: the created pending order
        """
        order = cls.objects.select_for_update().create(
            total_price_paid=0, purchaser=basket.user
        )
        total = 0
        now = now_in_utc()

        # apply all the discounts to the order first
        # this is needed to compute the discounted prices of each line
        for basket_discount in basket.discounts.all():
            order.discounts.create(
                redemption_date=now,
                redeemed_by=basket_discount.redeemed_by,
                redeemed_discount=basket_discount.redeemed_discount,
            )

        for basket_item in basket.basket_items.all():
            product = basket_item.product
            product_version = Version.objects.get_for_object(product).first()

            line = order.lines.create(
                order=order,
                product_version=product_version,
                quantity=1,
                purchased_object=product.purchasable_object,
            )

            total += line.discounted_price

        order.total_price_paid = total
        order.save()

        return order

    @transition(field="state", source=Order.STATE.PENDING, target=Order.STATE.FULFILLED)
    def fulfill(self, payment_data):
        """Fulfill this order"""
        from courses.api import create_run_enrollments

        # record the transaction
        self.transactions.create(
            data=payment_data,
            amount=self.total_price_paid,
        )

        # create enrollments for what the learner has paid for
        create_run_enrollments(
            self.purchaser,
            self.purchased_runs,
            mode=EDX_ENROLLMENT_VERIFIED_MODE,
            keep_failed_enrollments=True,
        )

    @transition(field="state", source=Order.STATE.PENDING, target=Order.STATE.CANCELED)
    def cancel(self):
        """Cancel this order"""
        pass

    @transition(field="state", source=Order.STATE.PENDING, target=Order.STATE.DECLINED)
    def decline(self):
        """Decline this order"""
        pass

    @transition(field="state", source=Order.STATE.PENDING, target=Order.STATE.ERRORED)
    def error(self):
        """Error this order"""
        pass

    @transition(field="state", source=Order.STATE.PENDING, target=Order.STATE.REVIEW)
    def review(self, payment_data):
        """
        Put the order into the review state. This should be mostly the same as
        fulfilling it but we don't want to do enrollments here (but we do want
        to store the transaction data, since there will technically be two of
        them).
        """
        self.transactions.create(data=payment_data, amount=self.total_price_paid)

    class Meta:
        proxy = True


class FulfilledOrder(Order):
    """An order that has a fulfilled payment"""

    @transition(
        field="state",
        source=Order.STATE.FULFILLED,
        target=Order.STATE.REFUNDED,
        custom=dict(admin=False),
    )
    def refund(self, amount: float, reason: str, unenroll_learner: bool):
        """
        Records the refund, and optionally attempts to unenroll the learner from
        the things they bought.

        Args:
            amount (float): the amount that was refunded
            reason (str): reason for refunding the order
            unenroll_learner (bool): also unenroll the learner (if possible)
        Returns:
            boolean: if unenroll_learner is set to True and the unenrollment
            fails, the unenrollment will still happen but this will return False
            to signify that it failed.
        """
        self.transactions.create(
            data={"reason": reason}, amount=amount, transaction_type="refund"
        )

        self.state = Order.STATE.REFUNDED

        unenrolls_successful = True

        if unenroll_learner:
            for run in self.purchased_runs:
                for enrollment in run.enrollments.filter(user=self.purchaser).all():
                    try:
                        if (
                            deactivate_run_enrollment(
                                enrollment, ENROLL_CHANGE_STATUS_REFUNDED
                            )
                            is None
                        ):
                            unenrolls_successful = False
                            deactivate_run_enrollment(
                                enrollment,
                                ENROLL_CHANGE_STATUS_REFUNDED,
                                keep_failed_enrollments=True,
                            )
                    except ObjectDoesNotExist:
                        pass

        return unenrolls_successful

    class Meta:
        proxy = True


class ReviewOrder(Order):
    """An order that has been placed under review by the payment processor."""

    @transition(field="state", source=Order.STATE.REVIEW, target=Order.STATE.FULFILLED)
    def fulfill(self, payment_data):
        """Fulfill this order"""
        from courses.api import create_run_enrollments

        # record the transaction
        self.transactions.create(
            data=payment_data,
            amount=self.total_price_paid,
        )

        # create enrollments for what the learner has paid for
        create_run_enrollments(
            self.purchaser,
            self.purchased_runs,
            mode=EDX_ENROLLMENT_VERIFIED_MODE,
        )

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


class DeclinedOrder(Order):
    """
    An order that is declined.

    The state of this can't be altered further.
    """

    class Meta:
        proxy = True


class ErroredOrder(Order):
    """
    An order that is errored.

    The state of this can't be altered further.
    """

    class Meta:
        proxy = True


class Line(TimestampedModel):
    """A line in an Order."""

    valid_purchasable_objects = valid_purchasable_objects_list()

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

    # denormalized reference which otherwise requires the lookup: line.product_version.product.purchasable_object
    purchased_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to=valid_purchasable_objects,
        null=True,
    )
    purchased_object_id = models.PositiveIntegerField(null=True)
    purchased_object = GenericForeignKey(
        "purchased_content_type", "purchased_object_id"
    )

    @property
    def item_description(self):
        return self.product_version.field_dict["description"]

    @property
    def content_type(self):
        return self.product_version.field_dict["content_type"]

    @property
    def unit_price(self):
        """Return the price of the product"""
        return self.product_version.field_dict["price"]

    @cached_property
    def total_price(self):
        """Return the price of the product"""
        return self.unit_price * self.quantity

    @cached_property
    def discounted_price(self):
        """Return the price of the product with discounts"""
        from ecommerce.discounts import DiscountType

        discounts = [
            discount_redemption.redeemed_discount
            for discount_redemption in self.order.discounts.all()
        ]

        return (
            DiscountType.get_discounted_price(
                discounts,
                Product.objects.get(pk=self.product_version.object_id),
                product_version=self.product_version,
            ).quantize(Decimal("0.01"))
            * self.quantity
        )

    @cached_property
    def product(self):
        from ecommerce.discounts import resolve_product_version

        return resolve_product_version(
            Product.objects.get(pk=self.product_version.field_dict["id"]),
            self.product_version,
        )

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
    transaction_type = models.TextField(
        choices=TRANSACTION_TYPES,
        default=TRANSACTION_TYPE_PAYMENT,
        null=False,
        max_length=20,
    )


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
        related_name="+",
    )
    redeemed_discount = models.ForeignKey(
        Discount, on_delete=models.CASCADE, related_name="+"
    )
    redeemed_basket = models.ForeignKey(
        Basket, on_delete=models.CASCADE, related_name="discounts"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["redeemed_by", "redeemed_basket"], name="unique_basket_discount"
            )
        ]

    def __str__(self):
        return f"{self.redemption_date}: {self.redeemed_discount}, {self.redeemed_by}"

    def convert_to_order(self, order: Order):
        """
        Converts basket discounts to order redemptions. Discounts
        applied to the basket are meant to be ephemeral; this makes them
        permanent.

        Args:
            - order (Order): The order to add the discount to.
        Returns:
            - DiscountRedemption for the converted redemption.
        """
        (redemption, isNew) = DiscountRedemption.objects.get_or_create(
            redemption_date=self.redemption_date,
            redeemed_by=self.redeemed_by,
            redeemed_discount=self.redeemed_discount,
            redeemed_order=order,
        )

        if isNew:
            redemption.save()

        return redemption


class DiscountRedemption(TimestampedModel):
    """
    Tracks when discounts were redeemed
    """

    redemption_date = models.DateTimeField()
    redeemed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="+",
    )
    redeemed_discount = models.ForeignKey(
        Discount, on_delete=models.CASCADE, related_name="order_redemptions"
    )
    redeemed_order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="discounts"
    )

    def __str__(self):
        return f"{self.redemption_date}: {self.redeemed_discount}, {self.redeemed_by}"
