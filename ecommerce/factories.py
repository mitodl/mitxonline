from factory import fuzzy, SubFactory
from factory.django import DjangoModelFactory
import faker

from courses.factories import CourseRunFactory
from ecommerce import models

FAKE = faker.Factory.create()


class ProductFactory(DjangoModelFactory):
    purchasable_object = SubFactory(CourseRunFactory)
    price = fuzzy.FuzzyDecimal(1, 2000, precision=2)
    description = FAKE.sentence(nb_words=4)
    is_active = True

    class Meta:
        model = models.Product
