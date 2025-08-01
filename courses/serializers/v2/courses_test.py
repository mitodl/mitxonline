import pytest
from django.contrib.auth.models import AnonymousUser
from django.http import QueryDict

from b2b.factories import (
    ContractPageFactory,
    OrganizationIndexPageFactory,
    OrganizationPageFactory,
)
from cms.serializers import CoursePageSerializer
from courses.factories import (
    CourseFactory,
    CourseRunEnrollmentFactory,
    CourseRunFactory,
    ProgramFactory,
)
from courses.models import CourseRunEnrollment, CoursesTopic, Department
from courses.serializers.v1.base import BaseProgramSerializer
from courses.serializers.v2.courses import (
    CourseRunEnrollmentSerializer,
    CourseRunSerializer,
    CourseWithCourseRunsSerializer,
)
from courses.views.v2 import UserEnrollmentFilterSet
from main.test_utils import assert_drf_json_equal

pytestmark = [pytest.mark.django_db]


@pytest.mark.parametrize("is_anonymous", [True, False])
@pytest.mark.parametrize("all_runs", [True, False])
@pytest.mark.parametrize(
    "certificate_type", ["MicroMasters Credential", "Certificate of Completion"]
)
def test_serialize_course(
    mocker, mock_context, is_anonymous, all_runs, certificate_type
):
    """Test Course serialization"""
    if is_anonymous:
        mock_context["request"].user = AnonymousUser()
    if all_runs:
        mock_context["all_runs"] = True
    user = mock_context["request"].user
    courseRun1 = CourseRunFactory.create()
    courseRun2 = CourseRunFactory.create(course=courseRun1.course)
    course = courseRun1.course
    topics = [CoursesTopic.objects.create(name=f"topic{num}") for num in range(3)]
    course.page.topics.set([topics[0], topics[1], topics[2]])
    department = "a course departments"
    course.departments.set([Department.objects.create(name=department)])
    program = ProgramFactory.create(program_type="Series")
    if certificate_type == "MicroMasters Credential":
        program.program_type = "MicroMasters®"
    program.add_requirement(course)
    program.save()

    CourseRunEnrollmentFactory.create(
        run=courseRun1, **({} if is_anonymous else {"user": user})
    )

    data = CourseWithCourseRunsSerializer(instance=course, context=mock_context).data

    assert_drf_json_equal(
        data,
        {
            "title": course.title,
            "readable_id": course.readable_id,
            "id": course.id,
            "courseruns": [
                CourseRunSerializer(run).data
                for run in sorted([courseRun1, courseRun2], key=lambda run: run.id)
            ],
            "next_run_id": course.first_unexpired_run.id,
            "max_weekly_hours": course.page.max_weekly_hours,
            "min_weekly_hours": course.page.min_weekly_hours,
            "departments": [{"name": department}],
            "page": CoursePageSerializer(course.page).data,
            "certificate_type": certificate_type,
            "availability": "dated",
            "topics": [{"name": topic.name} for topic in topics],
            "required_prerequisites": True,
            "duration": course.page.length,
            "max_weeks": course.page.max_weeks,
            "min_weeks": course.page.min_weeks,
            "min_price": course.page.min_price,
            "max_price": course.page.max_price,
            "time_commitment": course.page.effort,
            "programs": (
                BaseProgramSerializer(course.programs, many=True).data
                if all_runs
                else None
            ),
            "include_in_learn_catalog": course.page.include_in_learn_catalog,
            "ingest_content_files_for_ai": course.page.ingest_content_files_for_ai,
        },
    )


@pytest.mark.parametrize("prerequisites_cms_value", ["mock value", None, ""])
def test_serialize_course_required_prerequisites(
    mocker, mock_context, prerequisites_cms_value, settings
):
    """Test Course serialization to ensure that required_prerequisites is set to True if prerequisites is defined in the CMS and no an empty string, otherwise False"""
    course = CourseFactory.create()
    expected_required_prerequisites = False
    if prerequisites_cms_value is not None:
        # When prerequisites_cms_value is None, the course page has been created but prerequisites has never been populated.
        # If the prerequisites have previously been populated but are now empty, the value of prerequisites will be an empty string.
        course.page.prerequisites = prerequisites_cms_value
    if prerequisites_cms_value != "":
        expected_required_prerequisites = True

    data = CourseWithCourseRunsSerializer(instance=course, context=mock_context).data

    assert_drf_json_equal(
        data,
        {
            "title": course.title,
            "readable_id": course.readable_id,
            "id": course.id,
            "courseruns": [],
            "next_run_id": None,
            "max_weekly_hours": course.page.max_weekly_hours,
            "min_weekly_hours": course.page.min_weekly_hours,
            "departments": [],
            "page": CoursePageSerializer(course.page).data,
            "certificate_type": "Certificate of Completion",
            "topics": [],
            "availability": "anytime",
            "required_prerequisites": expected_required_prerequisites,
            "duration": course.page.length,
            "max_weeks": course.page.max_weeks,
            "min_weeks": course.page.min_weeks,
            "min_price": course.page.min_price,
            "max_price": course.page.max_price,
            "time_commitment": course.page.effort,
            "programs": None,
            "include_in_learn_catalog": course.page.include_in_learn_catalog,
            "ingest_content_files_for_ai": course.page.ingest_content_files_for_ai,
        },
    )


class TestCourseRunEnrollmentSerializerV2:
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
