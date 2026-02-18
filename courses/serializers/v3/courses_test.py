import pytest
from django.http import QueryDict

from b2b.factories import (
    ContractPageFactory,
    OrganizationIndexPageFactory,
    OrganizationPageFactory,
)
from courses.factories import (
    CourseRunEnrollmentFactory,
)
from courses.models import CourseRunEnrollment
from courses.serializers.v3.courses import (
    CourseRunEnrollmentSerializer,
)
from courses.views.v2 import UserEnrollmentFilterSet

pytestmark = [pytest.mark.django_db]


class TestCourseRunEnrollmentSerializerV3:
    """Test the v2 CourseRunEnrollmentSerializer."""

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
            "approved_flexible_price_exists",
            "certificate",
            "grades",
            "b2b_organization_id",
            "b2b_contract_id",
        }

        assert set(serialized_data.keys()) == expected_fields


class TestUserEnrollmentFiltering:
    """Test B2B filtering for user enrollments."""

    def test_exclude_b2b_filter_logic(self):
        """Test that the exclude_b2b filter correctly filters out B2B enrollments."""
        regular_enrollment = CourseRunEnrollmentFactory.create()

        org = OrganizationPageFactory.create(title="Test B2B Org")
        contract = ContractPageFactory.create(organization=org)
        b2b_enrollment = CourseRunEnrollmentFactory.create()
        b2b_enrollment.run.b2b_contract = contract
        b2b_enrollment.run.save()

        queryset = CourseRunEnrollment.objects.filter(
            id__in=[regular_enrollment.id, b2b_enrollment.id]
        )
        filter_set = UserEnrollmentFilterSet(QueryDict(), queryset=queryset)
        result = filter_set.qs
        assert result.count() == 2

        filter_data = QueryDict("exclude_b2b=true")
        filter_set = UserEnrollmentFilterSet(filter_data, queryset=queryset)
        result = filter_set.qs
        assert result.count() == 1
        assert result.first().id == regular_enrollment.id

        filter_data = QueryDict("exclude_b2b=false")
        filter_set = UserEnrollmentFilterSet(filter_data, queryset=queryset)
        result = filter_set.qs
        assert result.count() == 2

    def test_org_id_filter_logic(self):
        """Test that the org_id filter correctly filters by B2B organization."""
        org1_index_page = OrganizationIndexPageFactory.create(slug="org1")
        org1 = OrganizationPageFactory.create(
            title="Test Org 1", parent=org1_index_page, org_key="test-org-1"
        )
        org2_index_page = OrganizationIndexPageFactory.create(slug="org2")
        org2 = OrganizationPageFactory.create(
            title="Test Org 2", parent=org2_index_page, org_key="test-org-2"
        )

        contract1 = ContractPageFactory.create(organization=org1)
        contract2 = ContractPageFactory.create(organization=org2)

        enrollment1 = CourseRunEnrollmentFactory.create()
        enrollment1.run.b2b_contract = contract1
        enrollment1.run.save()

        enrollment2 = CourseRunEnrollmentFactory.create()
        enrollment2.run.b2b_contract = contract2
        enrollment2.run.save()

        queryset = CourseRunEnrollment.objects.all()
        filter_data = QueryDict(f"org_id={org1.id}")
        filter_set = UserEnrollmentFilterSet(filter_data, queryset=queryset)
        result = filter_set.qs
        assert result.count() == 1
        assert result.first().id == enrollment1.id

        filter_data = QueryDict(f"org_id={org2.id}")
        filter_set = UserEnrollmentFilterSet(filter_data, queryset=queryset)
        result = filter_set.qs
        assert result.count() == 1
        assert result.first().id == enrollment2.id
