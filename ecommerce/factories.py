from factory import fuzzy, SubFactory
from factory.django import DjangoModelFactory
import faker
import random

from courses.factories import CourseRunFactory
from ecommerce import models
from ecommerce.constants import ALL_DISCOUNT_TYPES, ALL_REDEMPTION_TYPES
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
    redemption_type = ALL_REDEMPTION_TYPES[
        random.randrange(0, len(ALL_REDEMPTION_TYPES), 1)
    ]

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
