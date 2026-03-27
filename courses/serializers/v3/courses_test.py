import pytest

from b2b.factories import (
    ContractPageFactory,
    OrganizationPageFactory,
)
from courses.factories import (
    CourseRunEnrollmentFactory,
)
from courses.serializers.v3.courses import (
    CourseRunEnrollmentSerializer,
)
from ecommerce.factories import ProductFactory

pytestmark = [pytest.mark.django_db]


class TestCourseRunEnrollmentSerializerV3:
    """Test the v3 CourseRunEnrollmentSerializer."""

    def test_serializer_without_b2b_contract(self):
        """Test serialization without B2B contract."""
        enrollment = CourseRunEnrollmentFactory.create()
        serialized_data = CourseRunEnrollmentSerializer(enrollment).data

        assert "b2b_organization_id" in serialized_data
        assert "b2b_contract_id" in serialized_data
        assert serialized_data["b2b_organization_id"] is None
        assert serialized_data["b2b_contract_id"] is None

    def test_serializer_with_b2b_contract(self):
        """Test serialization with B2B contract."""
        org = OrganizationPageFactory.create()
        contract = ContractPageFactory.create(organization=org)

        enrollment = CourseRunEnrollmentFactory.create()
        enrollment.run.b2b_contract = contract
        enrollment.run.save()

        serialized_data = CourseRunEnrollmentSerializer(enrollment).data
        assert serialized_data["b2b_organization_id"] == org.id
        assert serialized_data["b2b_contract_id"] == contract.id

    def test_serializer_fields(self):
        """Test that all expected fields are present."""
        enrollment = CourseRunEnrollmentFactory.create()
        serialized_data = CourseRunEnrollmentSerializer(enrollment).data

        expected_fields = {
            "run",
            "id",
            "edx_emails_subscription",
            "enrollment_mode",
            "certificate",
            "grades",
            "b2b_organization_id",
            "b2b_contract_id",
        }

        assert set(serialized_data.keys()) == expected_fields

    def test_serializer_includes_upgrade_fields_for_upgradable_run(self):
        """Test serialization includes denormalized upgrade fields when product is eligible."""
        enrollment = CourseRunEnrollmentFactory.create()
        product = ProductFactory.create(purchasable_object=enrollment.run)

        serialized_data = CourseRunEnrollmentSerializer(enrollment).data

        assert serialized_data["run"]["upgrade_product_id"] == product.id
        assert serialized_data["run"]["upgrade_product_price"] == str(product.price)
        assert serialized_data["run"]["upgrade_product_is_active"] is True

    def test_serializer_upgrade_fields_null_when_not_eligible(self):
        """Test upgrade fields are null if run has no eligible upgrade product."""
        enrollment = CourseRunEnrollmentFactory.create(run__upgrade_deadline=None)
        ProductFactory.create(purchasable_object=enrollment.run, is_active=False)

        serialized_data = CourseRunEnrollmentSerializer(enrollment).data

        assert serialized_data["run"]["upgrade_product_id"] is None
        assert serialized_data["run"]["upgrade_product_price"] is None
        assert serialized_data["run"]["upgrade_product_is_active"] is None
