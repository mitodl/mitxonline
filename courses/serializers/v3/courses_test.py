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


class TestCourseRunEnrollmentSerializerV3PaymentGuard:
    """Tests for payment guard in v3 CourseRunEnrollmentSerializer.create()."""

    def test_blocked_when_payment_required_and_not_paid(self):
        """Enrollment is rejected when all modes require payment and the user has not paid."""
        from rest_framework.exceptions import ValidationError  # noqa: PLC0415

        from courses.factories import (  # noqa: PLC0415
            CourseRunFactory,
            EnrollmentModeFactory,
        )
        from openedx.constants import EDX_ENROLLMENT_VERIFIED_MODE  # noqa: PLC0415
        from users.factories import UserFactory  # noqa: PLC0415

        user = UserFactory.create()
        run = CourseRunFactory.create(
            enrollment_modes=[
                EnrollmentModeFactory.create(
                    mode_slug=EDX_ENROLLMENT_VERIFIED_MODE, requires_payment=True
                )
            ]
        )
        serializer = CourseRunEnrollmentSerializer(
            data={"run_id": run.id}, context={"user": user}
        )
        assert serializer.is_valid(), serializer.errors
        with pytest.raises(ValidationError) as exc_info:
            serializer.save()
        assert "run_id" in exc_info.value.detail

    def test_allowed_when_audit_mode_available(self, mocker):
        """Free enrollment is permitted when the run has a free mode."""
        from courses.factories import (  # noqa: PLC0415
            CourseRunFactory,
            EnrollmentModeFactory,
        )
        from openedx.constants import EDX_ENROLLMENT_AUDIT_MODE  # noqa: PLC0415
        from users.factories import UserFactory  # noqa: PLC0415

        user = UserFactory.create()
        run = CourseRunFactory.create(
            enrollment_modes=[
                EnrollmentModeFactory.create(
                    mode_slug=EDX_ENROLLMENT_AUDIT_MODE, requires_payment=False
                )
            ]
        )
        mocker.patch(
            "courses.serializers.v3.courses.create_run_enrollments",
            return_value=([mocker.Mock()], True),
        )
        serializer = CourseRunEnrollmentSerializer(
            data={"run_id": run.id}, context={"user": user}
        )
        assert serializer.is_valid(), serializer.errors
        result = serializer.save()
        assert result is not None

    def test_allowed_when_user_has_paid(self, mocker):
        """Enrollment is permitted when all modes require payment but the user has paid."""
        from courses.factories import (  # noqa: PLC0415
            CourseRunFactory,
            EnrollmentModeFactory,
        )
        from courses.models import PaidCourseRun  # noqa: PLC0415
        from ecommerce.factories import OrderFactory  # noqa: PLC0415
        from ecommerce.models import OrderStatus  # noqa: PLC0415
        from openedx.constants import EDX_ENROLLMENT_VERIFIED_MODE  # noqa: PLC0415
        from users.factories import UserFactory  # noqa: PLC0415

        user = UserFactory.create()
        run = CourseRunFactory.create(
            enrollment_modes=[
                EnrollmentModeFactory.create(
                    mode_slug=EDX_ENROLLMENT_VERIFIED_MODE, requires_payment=True
                )
            ]
        )
        order = OrderFactory.create(purchaser=user, state=OrderStatus.FULFILLED)
        PaidCourseRun.objects.create(user=user, course_run=run, order=order)
        mocker.patch(
            "courses.serializers.v3.courses.create_run_enrollments",
            return_value=([mocker.Mock()], True),
        )
        serializer = CourseRunEnrollmentSerializer(
            data={"run_id": run.id}, context={"user": user}
        )
        assert serializer.is_valid(), serializer.errors
        result = serializer.save()
        assert result is not None
