import faker
import reversion
from factory import LazyAttribute, SubFactory, fuzzy
from factory.django import DjangoModelFactory
from reversion.models import Version

from courses.factories import CourseRunFactory, ProgramFactory
from ecommerce import models
from ecommerce.constants import (
    DISCOUNT_TYPE_PAID_AMOUNT_OFF,
    REDEMPTION_TYPE_ONE_TIME,
    REDEMPTION_TYPE_ONE_TIME_PER_USER,
    REDEMPTION_TYPE_PROGRAM_CHILD_PURCHASE,
    REDEMPTION_TYPE_UNLIMITED,
    STANDARD_DISCOUNT_TYPES,
    STANDARD_REDEMPTION_TYPES,
    ZERO_PAYMENT_DATA,
)
from main.utils import now_datetime_with_tz
from users.factories import UserFactory

FAKE = faker.Factory.create()


class ProductFactory(DjangoModelFactory):
    purchasable_object = SubFactory(CourseRunFactory)
    price = fuzzy.FuzzyDecimal(2, 2000, precision=2)
    description = FAKE.sentence(nb_words=4)
    is_active = True

    class Meta:
        model = models.Product


class ProgramProductFactory(DjangoModelFactory):
    purchasable_object = SubFactory(ProgramFactory)
    price = fuzzy.FuzzyDecimal(2, 2000, precision=2)
    description = FAKE.sentence(nb_words=4)
    is_active = True

    class Meta:
        model = models.Product


class DiscountFactory(DjangoModelFactory):
    amount = fuzzy.FuzzyInteger(1, 49)
    discount_type = fuzzy.FuzzyChoice(STANDARD_DISCOUNT_TYPES)
    discount_code = fuzzy.FuzzyText(length=20)
    redemption_type = fuzzy.FuzzyChoice(STANDARD_REDEMPTION_TYPES)
    payment_type = None

    class Meta:
        model = models.Discount


# One factory per redemption type, so tests can name the ruleset they exercise.


class OneTimeDiscountFactory(DiscountFactory):
    redemption_type = REDEMPTION_TYPE_ONE_TIME


class OneTimePerUserDiscountFactory(DiscountFactory):
    redemption_type = REDEMPTION_TYPE_ONE_TIME_PER_USER


class UnlimitedUseDiscountFactory(DiscountFactory):
    redemption_type = REDEMPTION_TYPE_UNLIMITED


class SetLimitDiscountFactory(DiscountFactory):
    redemption_type = REDEMPTION_TYPE_UNLIMITED
    max_redemptions = fuzzy.FuzzyInteger(1, 4)


class PaidAmountOffDiscountFactory(DiscountFactory):
    amount = 0
    discount_type = DISCOUNT_TYPE_PAID_AMOUNT_OFF
    redemption_type = REDEMPTION_TYPE_PROGRAM_CHILD_PURCHASE
    automatic = True


class BasketFactory(DjangoModelFactory):
    """Factory for Basket"""

    user = SubFactory(UserFactory)

    class Meta:
        model = models.Basket


class BasketItemFactory(DjangoModelFactory):
    """Factory for BasketItem"""

    product = SubFactory(ProductFactory)

    basket = SubFactory(BasketFactory)

    class Meta:
        model = models.BasketItem


class OrderFactory(DjangoModelFactory):
    total_price_paid = fuzzy.FuzzyDecimal(10.00, 10.00)
    purchaser = SubFactory(UserFactory)
    state = models.OrderStatus.PENDING

    class Meta:
        model = models.Order


class TransactionFactory(DjangoModelFactory):
    order = SubFactory(OrderFactory)
    amount = fuzzy.FuzzyDecimal(10.00, 10.00)
    data = ZERO_PAYMENT_DATA

    class Meta:
        model = models.Transaction


class LineFactory(DjangoModelFactory):
    quantity = 1
    order = SubFactory(OrderFactory)
    purchased_object = SubFactory(CourseRunFactory)
    # discounted_unit_price is non-null, so price the line the way the app does:
    # under whatever discounts the order carries when the line is built.
    discounted_unit_price = LazyAttribute(
        lambda line: models.Line.compute_discounted_unit_price_for(
            line.order, line.product_version
        )
    )

    class Meta:
        model = models.Line


class DiscountRedemptionFactory(DjangoModelFactory):
    redeemed_by = SubFactory(UserFactory)
    redeemed_discount = SubFactory(DiscountFactory)
    redeemed_order = SubFactory(OrderFactory)
    redemption_date = now_datetime_with_tz()

    class Meta:
        model = models.DiscountRedemption


def make_purchase(
    user,
    purchasable,
    price,
    *,
    paid=None,
    state=models.OrderStatus.FULFILLED,
):
    """
    An order for ``purchasable`` with one line listed at ``price`` and charged
    ``paid`` (defaults to ``price``). Returns the Line.

    The Product is created inside a revision because Line.product_version is
    non-null and reversion only records a Version for objects saved under one.
    """
    with reversion.create_revision():
        product = ProductFactory.create(purchasable_object=purchasable, price=price)
    charged = price if paid is None else paid
    order = OrderFactory.create(purchaser=user, state=state, total_price_paid=charged)
    return models.Line.objects.create(
        order=order,
        purchased_object_id=product.object_id,
        purchased_content_type_id=product.content_type_id,
        product_version=Version.objects.get_for_object(product).first(),
        quantity=1,
        discounted_unit_price=charged,
    )
