import pytest
from main.test_utils import assert_drf_json_equal, drf_datetime

from courses.factories import (
    CourseRunFactory,
    ProgramFactory,
    ProgramRunFactory,
)

from ecommerce.serializers import (
    ProductSerializer,
    CourseRunProductPurchasableObjectSerializer,
    ProgramRunProductPurchasableObjectSerializer,
)
from ecommerce.factories import ProductFactory

pytestmark = [pytest.mark.django_db]


def test_product_course_serializer(mock_context):
    """
    Tests serialization of a product that has an associated course.
    """
    program = ProgramFactory.create()
    run = CourseRunFactory.create(course__program=program)
    product = ProductFactory.create(purchasable_object=run)
    product_serialized = ProductSerializer(instance=product).data
    run_serialized = CourseRunProductPurchasableObjectSerializer(instance=run).data

    assert_drf_json_equal(
        product_serialized,
        {
            "description": product.description,
            "id": product.id,
            "is_active": product.is_active,
            "price": str(product.price),
            "purchasable_object": run_serialized,
        },
    )


def test_product_program_serializer(mock_context):
    """
    Tests serialization of a product that has an associated program.
    """
    run = ProgramRunFactory.create()
    product = ProductFactory.create(purchasable_object=run)
    product_serialized = ProductSerializer(instance=product).data
    run_serialized = ProgramRunProductPurchasableObjectSerializer(instance=run).data

    assert_drf_json_equal(
        product_serialized,
        {
            "description": product.description,
            "id": product.id,
            "is_active": product.is_active,
            "price": str(product.price),
            "purchasable_object": run_serialized,
        },
    )
