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


def serialize(enrollment, *, has_course_staff_role=False):
    """
    Serialize an enrollment the way the viewset's queryset would.

    `has_course_staff_role` comes from an annotation on
    UserEnrollmentsApiViewSet.get_queryset, and the serializer reads it
    directly, so a factory object has to carry it too.
    """
    enrollment.has_course_staff_role = has_course_staff_role
    return CourseRunEnrollmentSerializer(enrollment).data


class TestCourseRunEnrollmentSerializerV3:
    """Test the v3 CourseRunEnrollmentSerializer."""

    def test_serializer_without_b2b_contract(self):
        """Test serialization without B2B contract."""
        enrollment = CourseRunEnrollmentFactory.create()
        serialized_data = serialize(enrollment)

        assert "b2b_organization_id" in serialized_data
        assert "b2b_contract_id" in serialized_data
        assert serialized_data["b2b_organization_id"] is None
        assert serialized_data["b2b_contract_id"] is None

    def test_serializer_with_b2b_contract(self):
        """Test serialization with B2B contract."""
        org = OrganizationPageFactory.create()
        contract = ContractPageFactory.create(organization=org)

        enrollment = CourseRunEnrollmentFactory.create(
            run__b2b_contracts=[contract], b2b_contract=contract
        )

        serialized_data = serialize(enrollment)
        assert serialized_data["b2b_organization_id"] == org.id
        assert serialized_data["b2b_contract_id"] == contract.id

    @pytest.mark.parametrize("annotated", [True, False])
    def test_has_course_staff_role_reflects_the_annotation(self, annotated):
        """The field reports the annotation the viewset's queryset attaches."""
        enrollment = CourseRunEnrollmentFactory.create()

        assert (
            serialize(enrollment, has_course_staff_role=annotated)[
                "has_course_staff_role"
            ]
            is annotated
        )

    def test_unannotated_enrollment_fails_loudly(self):
        """
        Serializing without the annotation raises rather than reporting False.

        A silent False would be indistinguishable from a learner who genuinely
        holds no role, which is the bug this guards.
        """
        enrollment = CourseRunEnrollmentFactory.create()

        with pytest.raises(AttributeError):
            CourseRunEnrollmentSerializer(enrollment).data  # noqa: B018

    def test_serializer_fields(self):
        """Test that all expected fields are present."""
        enrollment = CourseRunEnrollmentFactory.create()
        serialized_data = serialize(enrollment)

        expected_fields = {
            "run",
            "id",
            "edx_emails_subscription",
            "enrollment_mode",
            "certificate",
            "grades",
            "b2b_organization_id",
            "b2b_contract_id",
            "has_course_staff_role",
        }

        assert set(serialized_data.keys()) == expected_fields

    def test_serializer_includes_upgrade_fields_for_upgradable_run(self):
        """Test serialization includes denormalized upgrade fields when product is eligible."""
        enrollment = CourseRunEnrollmentFactory.create()
        product = ProductFactory.create(purchasable_object=enrollment.run)

        serialized_data = serialize(enrollment)

        assert serialized_data["run"]["upgrade_product_id"] == product.id
        assert serialized_data["run"]["upgrade_product_price"] == str(product.price)
        assert serialized_data["run"]["upgrade_product_is_active"] is True

    def test_serializer_upgrade_fields_null_when_not_eligible(self):
        """Test upgrade fields are null if run has no eligible upgrade product."""
        enrollment = CourseRunEnrollmentFactory.create(run__upgrade_deadline=None)
        ProductFactory.create(purchasable_object=enrollment.run, is_active=False)

        serialized_data = serialize(enrollment)

        assert serialized_data["run"]["upgrade_product_id"] is None
        assert serialized_data["run"]["upgrade_product_price"] is None
        assert serialized_data["run"]["upgrade_product_is_active"] is None
