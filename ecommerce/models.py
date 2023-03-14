import logging
import uuid
from datetime import datetime
from decimal import Decimal

import pytz
import reversion
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils.functional import cached_property
from django_fsm import FSMField, transition
from mitol.common.models import TimestampedModel
from mitol.common.utils.datetime import now_in_utc
from reversion.models import Version

from courses.api import create_run_enrollments
from courses.models import CourseRun, PaidCourseRun
from ecommerce.constants import (
    DISCOUNT_TYPE_DOLLARS_OFF,
    DISCOUNT_TYPE_FIXED_PRICE,
    DISCOUNT_TYPE_PERCENT_OFF,
    DISCOUNT_TYPES,
    PAYMENT_TYPES,
    REDEMPTION_TYPE_ONE_TIME,
    REDEMPTION_TYPE_ONE_TIME_PER_USER,
    REDEMPTION_TYPE_UNLIMITED,
    REDEMPTION_TYPES,
    REFERENCE_NUMBER_PREFIX,
    TRANSACTION_TYPE_PAYMENT,
    TRANSACTION_TYPE_REFUND,
    TRANSACTION_TYPES,
)
from ecommerce.tasks import send_ecommerce_order_receipt, send_order_refund_email
from main.settings import TIME_ZONE
from openedx.constants import EDX_ENROLLMENT_VERIFIED_MODE
from users.models import User

User = get_user_model()


def valid_purchasable_objects_list():
    return models.Q(app_label="courses", model="courserun") | models.Q(
        app_label="courses", model="programrun"
    )


class ProductsQuerySet(models.QuerySet):
    """Queryset to block delete and instead mark the items in_active"""

    def delete(self):
        self.update(is_active=False)


class ActiveUndeleteManager(models.Manager):
    """Query manager for active objects"""

    # This can be used generally, for the models that have `is_active` field
    def get_queryset(self):
        """Getting the active queryset for manager"""
        return ProductsQuerySet(self.model, using=self._db).filter(is_active=True)


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

    objects = ActiveUndeleteManager()
    all_objects = models.Manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["object_id", "is_active", "content_type"],
                condition=models.Q(is_active=True),
                name="unique_purchasable_object",
            )
        ]

    def delete(self):
        self.is_active = False
        self.save(update_fields=("is_active",))

    def __str__(self):
        return f"#{self.id} {self.description} {self.price}"


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

    def has_user_purchased_same_courserun(self, user):
        """
        Return true if any of the courses in the basket has already purchased
        """
        basket_items = self.basket_items.prefetch_related("product")
        for item in basket_items:
            purchased_object = item.product.purchasable_object
            if isinstance(purchased_object, CourseRun):
                # PaidCourseRun should only contain fulfilled orders
                if PaidCourseRun.fulfilled_paid_course_run_exists(
                    user, purchased_object
                ):
                    return True

        return False

    def has_user_purchased_non_upgradable_courserun(self):
        """
        Return true if any of the courses in the basket can not be Upgraded/Purchased because of past upgrade_deadline
        """
        basket_items = self.basket_items.prefetch_related("product")
        for item in basket_items:
            purchased_object = item.product.purchasable_object
            # If the upgrade_deadline has passed for a course it should not be purchased if it was in basket
            return (
                isinstance(purchased_object, CourseRun)
                and not purchased_object.is_upgradable
            )

        return False

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

    def get_products(self):
        """
        Returns the products that have been added to the basket so far.
        """

        return [item.product for item in self.basket_items.all()]


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
    payment_type = models.CharField(null=True, choices=PAYMENT_TYPES, max_length=30)
    max_redemptions = models.PositiveIntegerField(null=True, default=0)
    discount_code = models.CharField(max_length=50)
    activation_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="If set, this discount code will not be redeemable before this date.",
    )
    expiration_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="If set, this discount code will not be redeemable after this date.",
    )

    def __str__(self):
        return f"{self.amount} {self.discount_type} {self.redemption_type} - {self.discount_code}"

    @cached_property
    def is_redeemed(self):
        return DiscountRedemption.objects.filter(redeemed_discount=self).exists()

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
            and DiscountRedemption.objects.filter(
                redeemed_discount=self,
                redeemed_order__state=Order.STATE.FULFILLED,
            ).count()
            > 0
        ):
            return False

        if (
            self.redemption_type == REDEMPTION_TYPE_ONE_TIME_PER_USER
            and DiscountRedemption.objects.filter(
                redeemed_discount=self,
                redeemed_order__state=Order.STATE.FULFILLED,
                redeemed_by=user,
            ).count()
            > 0
        ):
            return False

        if (
            self.max_redemptions > 0
            and DiscountRedemption.objects.filter(
                redeemed_discount=self,
                redeemed_order__state=Order.STATE.FULFILLED,
            ).count()
            >= self.max_redemptions
        ):
            return False

        return self.valid_now()

    def check_validity_with_products(self, products: list):
        """
        Checks if the discount is valid for product
        Returns True if there is no product attached to the discount or if all the products
        are attached with the discount else False.
        Args:
            products (list): List of products.
        Returns:
            Boolean
        """
        if self.products.exists() and not (
            self.products.filter(product__in=products).exists()
        ):
            return False

        return self.valid_now()

    def valid_now(self):
        """Returns True if the discount is valid right now"""
        if self.activation_date is not None and self.activation_date > datetime.now(
            pytz.timezone(TIME_ZONE)
        ):
            return False

        if self.expiration_date is not None and self.expiration_date <= datetime.now(
            pytz.timezone(TIME_ZONE)
        ):
            return False

        return True

    def friendly_format(self):
        amount = "{:.2f}".format(self.amount)

        if self.discount_type == DISCOUNT_TYPE_PERCENT_OFF:
            return f"{amount}% off"
        elif self.discount_type == DISCOUNT_TYPE_DOLLARS_OFF:
            return f"${amount} off"
        elif self.discount_type == DISCOUNT_TYPE_FIXED_PRICE:
            return f"a fixed price of ${amount}"

        return "Indeterminate Discount"

    def discount_product(self, product, user=None):
        """
        Returns the calculated discount amount for a given product.

        Args:
            product (Product): the product to discount
            user (User or None): the current user
        Returns:
            Number; the calculated amount of the discounts
        """
        from ecommerce.discounts import DiscountType

        if (user is None and self.valid_now()) or self.check_validity(user):
            return DiscountType.get_discounted_price([self], product).quantize(
                Decimal("0.01")
            )


class DiscountProduct(TimestampedModel):
    discount = models.ForeignKey(
        Discount, on_delete=models.CASCADE, related_name="products"
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="discounts",
        blank=True,
        null=True,
    )

    def __str__(self):
        return f"Discount {self.discount.discount_code} for product {self.product.purchasable_object}"


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
        PARTIALLY_REFUNDED = "partially_refunded"

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
                (
                    cls.PARTIALLY_REFUNDED,
                    "Partially Refunded",
                    "PartiallyRefundedOrder",
                ),
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
    reference_number = models.CharField(max_length=255, null=True, blank=True)

    # override save method to auto-fill generated_rerefence_number
    def save(self, *args, **kwargs):
        from hubspot_sync.task_helpers import sync_hubspot_deal

        # initial save in order to get primary key for new order
        super().save(*args, **kwargs)

        # can't insert twice because it'll try to insert with a PK now
        kwargs.pop("force_insert", None)

        # if we don't have a generated reference number, we generate one and save again
        if self.reference_number is None:
            self.reference_number = self._generate_reference_number()
            super().save(*args, **kwargs)
        sync_hubspot_deal(self)

    # Flag to determine if the order is in review status - if it is, then
    # we need to not step on the basket that may or may not exist when it is
    # accepted
    @property
    def is_review(self):
        return self.state == Order.STATE.REVIEW

    @property
    def is_fulfilled(self):
        return self.state == Order.STATE.FULFILLED

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

    def refund(self, *, api_response_data, **kwargs):
        """Issue a refund"""
        raise NotImplementedError()

    def _generate_reference_number(self):
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


class FulfillableOrder:
    """class to handle common logics like fulfill, enrollment etc"""

    def create_transaction(self, payment_data):
        log = logging.getLogger(__name__)
        transaction_id = payment_data.get("transaction_id")
        amount = payment_data.get("amount")
        # There are two use cases:
        # No payment required - no cybersource involved, so we need to generate UUID as transaction id
        # Payment STATE_ACCEPTED - there should always be transaction_id in payment data, if not, throw ValidationError
        if amount == 0 and transaction_id is None:
            transaction_id = uuid.uuid1()
        elif transaction_id is None:
            raise ValidationError(
                "Failed to record transaction: Missing transaction id from payment API response"
            )

        self.transactions.get_or_create(
            transaction_id=transaction_id,
            data=payment_data,
            amount=self.total_price_paid,
        )

    def create_paid_courseruns(self):
        for run in self.purchased_runs:
            PaidCourseRun.objects.get_or_create(
                order=self, course_run=run, user=self.purchaser
            )

    def create_enrollments(self):
        # create enrollments for what the learner has paid for
        create_run_enrollments(
            self.purchaser,
            self.purchased_runs,
            mode=EDX_ENROLLMENT_VERIFIED_MODE,
            keep_failed_enrollments=True,
        )

    def send_ecommerce_order_receipt(self):
        send_ecommerce_order_receipt.delay(self.id)

    @transition(
        field="state",
        source=Order.STATE.PENDING,
        target=Order.STATE.FULFILLED,
    )
    def fulfill(self, payment_data, already_enrolled=False):
        # record the transaction
        self.create_transaction(payment_data)

        # if user already enrolled from management command it'll not recreate
        if not already_enrolled:
            # create enrollments for what the learner has paid for
            self.create_enrollments()

        # record all the courseruns in the order
        self.create_paid_courseruns()

        # No email is required as this order is generated from management command
        if not already_enrolled:
            # send the receipt emails
            transaction.on_commit(self.send_ecommerce_order_receipt)


class PendingOrder(FulfillableOrder, Order):
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

        for product in basket.get_products():
            product_version = Version.objects.get_for_object(product).first()

            line, created = order.lines.get_or_create(
                order=order,
                purchased_object_id=product.object_id,
                purchased_content_type_id=product.content_type_id,
                defaults=dict(
                    product_version=product_version,
                    quantity=1,
                ),
            )
            if created:
                total += line.discounted_price

        order.total_price_paid = total
        order.save()

        return order

    @classmethod
    @transaction.atomic()
    def create_from_product(cls, product: Product, user: User, discount: Discount):
        """
        Creates a new pending order from a product

        Args:
            product (Product):  the product to create an order for
            user (User):  the user to create an order for
            discount (Discount):  the discount code to create an order discount redemption

        Returns:
            PendingOrder: the created pending order
        """
        order = cls.objects.select_for_update().create(
            total_price_paid=0, purchaser=user
        )
        total = 0
        now = now_in_utc()

        # apply all the discounts to the order first
        # this is needed to compute the discounted prices of each line
        order.discounts.create(
            redemption_date=now,
            redeemed_by=user,
            redeemed_discount=discount,
        )

        product_version = Version.objects.get_for_object(product).first()

        line, created = order.lines.get_or_create(
            order=order,
            purchased_object_id=product.object_id,
            purchased_content_type_id=product.content_type_id,
            defaults=dict(
                product_version=product_version,
                quantity=1,
            ),
        )
        if created:
            total += line.discounted_price

        order.total_price_paid = total
        order.save()

        return order

    @transition(field="state", source=Order.STATE.PENDING, target=Order.STATE.CANCELED)
    def cancel(self):
        """Cancel this order"""
        pass

    @transition(field="state", source=Order.STATE.PENDING, target=Order.STATE.DECLINED)
    def decline(self):
        """
        Decline this order. This additionally clears the discount redemptions
        for the order so the discounts can be reused.
        """
        for redemption in self.discounts.all():
            redemption.delete()

        self.state = Order.STATE.DECLINED
        self.save()

        return self

    @transition(field="state", source=Order.STATE.PENDING, target=Order.STATE.ERRORED)
    def error(self):
        """Error this order"""
        pass

    class Meta:
        proxy = True


class FulfilledOrder(Order):
    """An order that has a fulfilled payment"""

    @transition(field="state", source=Order.STATE.FULFILLED, target=Order.STATE.ERRORED)
    def error(self):
        """Error this order"""
        pass

    @transition(
        field="state",
        source=Order.STATE.FULFILLED,
        target=Order.STATE.REFUNDED,
        custom=dict(admin=False),
    )
    def refund(self, *, api_response_data: dict = None, **kwargs):
        """
        Records the refund, and optionally attempts to unenroll the learner from
        the things they bought.

        Args:
            api_response_data (dict): In case of API response we will have the response data dictionary
            kwargs: Ideally it should have named parameters such as
            1- amount: that was refunded
            2- reason: for refunding the order

            at hand with enough details, So when the dict is passed we would save it as is,
            otherwise fallback to default dict creation below
        Returns:
            Object (Transaction): return the refund transaction object for the refund.
        """
        amount = kwargs.get("amount")
        reason = kwargs.get("reason")

        transaction_id = api_response_data.get("id")
        if transaction_id is None:
            raise ValidationError(
                "Failed to record transaction: Missing transaction id from refund API response"
            )

        refund_transaction, created = self.transactions.get_or_create(
            transaction_id=transaction_id,
            data=api_response_data,
            amount=amount,
            transaction_type=TRANSACTION_TYPE_REFUND,
            reason=reason,
        )
        self.state = Order.STATE.REFUNDED
        self.save()

        send_order_refund_email.delay(self.id)

        return refund_transaction

    class Meta:
        proxy = True


class ReviewOrder(FulfillableOrder, Order):
    """An order that has been placed under review by the payment processor."""

    class Meta:
        proxy = True


class CanceledOrder(Order):
    """
    An order that is canceled.

    The state of this can't be altered further.
    """

    @transition(field="state", source=Order.STATE.CANCELED, target=Order.STATE.ERRORED)
    def error(self):
        """Error this order"""
        pass

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

    @transition(field="state", source=Order.STATE.DECLINED, target=Order.STATE.ERRORED)
    def error(self):
        """Error this order"""
        pass

    class Meta:
        proxy = True


class ErroredOrder(Order):
    """
    An order that is errored.

    The state of this can't be altered further.
    """

    class Meta:
        proxy = True


class PartiallyRefundedOrder(Order):
    """
    An order that is partially refunded.

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

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["order_id", "purchased_content_type", "purchased_object_id"],
                name="unique_order_purchased_object",
            )
        ]

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
                Product.all_objects.get(pk=self.product_version.object_id),
                product_version=self.product_version,
            ).quantize(Decimal("0.01"))
            * self.quantity
        )

    @cached_property
    def product(self):
        from ecommerce.discounts import resolve_product_version

        return resolve_product_version(
            Product.all_objects.get(pk=self.product_version.field_dict["id"]),
            self.product_version,
        )

    def __str__(self):
        return f"{self.product_version}"


class Transaction(TimestampedModel):
    """A transaction on an order, generally a payment but can also cover refunds"""

    # Per CyberSourse, Request ID should be 22 digits
    transaction_id = models.CharField(max_length=255, unique=True)

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
    reason = models.CharField(max_length=255, blank=True)


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
