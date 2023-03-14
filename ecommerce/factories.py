import random

import faker
from factory import SubFactory, fuzzy
from factory.django import DjangoModelFactory

from courses.factories import CourseRunFactory
from ecommerce import models
from ecommerce.constants import (
    ALL_DISCOUNT_TYPES,
    ALL_REDEMPTION_TYPES,
    REDEMPTION_TYPE_ONE_TIME,
    REDEMPTION_TYPE_ONE_TIME_PER_USER,
    REDEMPTION_TYPE_UNLIMITED,
)
from main.utils import now_datetime_with_tz
from users.factories import UserFactory

FAKE = faker.Factory.create()


class ProductFactory(DjangoModelFactory):
    purchasable_object = SubFactory(CourseRunFactory)
    price = fuzzy.FuzzyDecimal(1, 2000, precision=2)
    description = FAKE.sentence(nb_words=4)
    is_active = True

    class Meta:
        model = models.Product


class DiscountFactory(DjangoModelFactory):
    amount = random.randrange(1, 50, 1)
    discount_type = ALL_DISCOUNT_TYPES[random.randrange(0, len(ALL_DISCOUNT_TYPES), 1)]
    discount_code = fuzzy.FuzzyText(length=20)
    redemption_type = ALL_REDEMPTION_TYPES[
        random.randrange(0, len(ALL_REDEMPTION_TYPES), 1)
    ]
    payment_type = None

    class Meta:
        model = models.Discount


# Four factories here to test the redemption ruleset


class OneTimeDiscountFactory(DjangoModelFactory):
    amount = random.randrange(1, 50, 1)
    discount_type = ALL_DISCOUNT_TYPES[random.randrange(0, len(ALL_DISCOUNT_TYPES), 1)]
    discount_code = fuzzy.FuzzyText(length=20)
    redemption_type = REDEMPTION_TYPE_ONE_TIME

    class Meta:
        model = models.Discount


class OneTimePerUserDiscountFactory(DjangoModelFactory):
    amount = random.randrange(1, 50, 1)
    discount_type = ALL_DISCOUNT_TYPES[random.randrange(0, len(ALL_DISCOUNT_TYPES), 1)]
    discount_code = fuzzy.FuzzyText(length=20)
    redemption_type = REDEMPTION_TYPE_ONE_TIME_PER_USER

    class Meta:
        model = models.Discount


class UnlimitedUseDiscountFactory(DjangoModelFactory):
    amount = random.randrange(1, 50, 1)
    discount_type = ALL_DISCOUNT_TYPES[random.randrange(0, len(ALL_DISCOUNT_TYPES), 1)]
    discount_code = fuzzy.FuzzyText(length=20)
    redemption_type = REDEMPTION_TYPE_UNLIMITED

    class Meta:
        model = models.Discount


class SetLimitDiscountFactory(DjangoModelFactory):
    amount = random.randrange(1, 50, 1)
    discount_type = ALL_DISCOUNT_TYPES[random.randrange(0, len(ALL_DISCOUNT_TYPES), 1)]
    discount_code = fuzzy.FuzzyText(length=20)
    redemption_type = REDEMPTION_TYPE_UNLIMITED
    max_redemptions = random.randrange(1, 5, 1)

    class Meta:
        model = models.Discount


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

    class Meta:
        model = models.Order


class TransactionFactory(DjangoModelFactory):
    order = SubFactory(OrderFactory)
    amount = fuzzy.FuzzyDecimal(10.00, 10.00)

    class Meta:
        model = models.Transaction


class LineFactory(DjangoModelFactory):
    quantity = 1

    class Meta:
        model = models.Line


class DiscountRedemptionFactory(DjangoModelFactory):
    redeemed_by = SubFactory(UserFactory)
    redeemed_discount = SubFactory(DiscountFactory)
    redeemed_order = SubFactory(OrderFactory)
    redemption_date = now_datetime_with_tz()

    class Meta:
        model = models.DiscountRedemption
