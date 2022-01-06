import pytest
import random
from main.test_utils import assert_drf_json_equal
from django.urls import reverse
import operator as op

from ecommerce.serializers import (
    ProductSerializer,
)
from ecommerce.factories import ProductFactory

pytestmark = [pytest.mark.django_db]


@pytest.fixture()
def products():
    return ProductFactory.create_batch(5)


def test_list_products(user_drf_client, products):
    resp = user_drf_client.get(reverse("products_api-list"), {"l": 10, "o": 0})
    resp_products = sorted(resp.json()["results"], key=op.itemgetter("id"))

    assert len(resp_products) == len(products)

    for product, resp_product in zip(products, resp_products):
        assert_drf_json_equal(resp_product, ProductSerializer(product).data)


def test_get_products(user_drf_client, products):
    product = products[random.randrange(0, len(products))]

    resp = user_drf_client.get(
        reverse("products_api-detail", kwargs={"pk": product.id})
    )

    assert_drf_json_equal(resp.json(), ProductSerializer(product).data)
