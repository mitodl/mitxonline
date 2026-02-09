"""
Tests for courses api views v2
"""

import logging
import random
import uuid
from datetime import timedelta

import pytest
import responses
import reversion
from anys import ANY_STR
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.db.models import Q
from django.test.client import RequestFactory
from django.urls import reverse
from faker import Faker
from mitol.common.utils import now_in_utc
from rest_framework import status
from rest_framework.request import Request
from rest_framework.test import APIClient

from b2b.api import create_contract_run
from b2b.factories import ContractPageFactory, OrganizationPageFactory
from b2b.models import ContractProgramItem
from cms.factories import CoursePageFactory, ProgramPageFactory
from cms.serializers import ProgramPageSerializer
from courses.constants import ENROLL_CHANGE_STATUS_UNENROLLED
from courses.factories import (
    CourseFactory,
    CourseRunCertificateFactory,
    CourseRunEnrollmentFactory,
    CourseRunFactory,
    DepartmentFactory,
    ProgramCertificateFactory,
    ProgramEnrollmentFactory,
    ProgramFactory,
)
from courses.models import (
    Course,
    CourseRunEnrollment,
    Program,
    ProgramEnrollment,
)
from courses.serializers.v2.certificates import (
    CourseRunCertificateSerializer,
    ProgramCertificateSerializer,
)
from courses.serializers.v2.courses import (
    CourseRunWithCourseSerializer,
    CourseWithCourseRunsSerializer,
)
from courses.serializers.v2.departments import (
    DepartmentWithCoursesAndProgramsSerializer,
)
from courses.serializers.v2.programs import (
    ProgramRequirementTreeSerializer,
    ProgramSerializer,
)
from courses.test_utils import maybe_serialize_course_cert, maybe_serialize_program_cert
from courses.utils import (
    get_enrollable_courses,
    get_unenrollable_courses,
)
from courses.views.test_utils import (
    num_queries_from_course,
    num_queries_from_department,
    num_queries_from_programs,
)
from courses.views.v2 import Pagination, ProgramFilterSet
from ecommerce.models import Product
from main import features
from main.test_utils import assert_drf_json_equal, duplicate_queries_check
from openedx.constants import EDX_ENROLLMENT_AUDIT_MODE, EDX_ENROLLMENT_VERIFIED_MODE
from users.factories import UserFactory

pytestmark = [pytest.mark.django_db]
logger = logging.getLogger(__name__)
faker = Faker()


@pytest.mark.skip_nplusone_check
@pytest.mark.parametrize("course_catalog_course_count", [100], indirect=True)
@pytest.mark.parametrize("course_catalog_program_count", [12], indirect=True)
def test_get_programs(
    user_drf_client, django_assert_max_num_queries, course_catalog_data
):
    """Test the view that handles requests for all Programs"""
    course_catalog_data  # noqa: B018

    # Fetch programs after running the fixture so they're in the right order
    programs = Program.objects.order_by("title").prefetch_related("departments").all()
    program_ids = programs.values_list("title", flat=True).all()

    num_queries = num_queries_from_programs(programs, "v2")
    with django_assert_max_num_queries(num_queries) as context:
        resp = user_drf_client.get(reverse("v2:programs_api-list"))
    duplicate_queries_check(context)
    programs_data = resp.json()["results"]
    assert len(programs_data) == Pagination.page_size
    # Assert that things are in the correct order by checking the IDs
    assert [result["title"] for result in programs_data] == list(program_ids)

    for program_data in programs_data:
        program = programs.get(pk=program_data["id"])
        # Clear cached property to ensure consistent data between API and serializer
        if hasattr(program, "_courses_with_requirements_data"):
            delattr(program, "_courses_with_requirements_data")
        assert_drf_json_equal(
            program_data, ProgramSerializer(program).data, ignore_order=True
        )


@pytest.mark.parametrize("course_catalog_course_count", [100], indirect=True)
@pytest.mark.parametrize("course_catalog_program_count", [15], indirect=True)
def test_get_departments(
    user_drf_client, mock_context, django_assert_max_num_queries, course_catalog_data
):
    departments = DepartmentFactory.create_batch(size=10)
    empty_departments_from_fixture = []
    for department in departments:
        empty_departments_from_fixture.append(  # noqa: PERF401
            DepartmentWithCoursesAndProgramsSerializer(
                instance=department, context=mock_context
            ).data
        )
    with django_assert_max_num_queries(
        num_queries_from_department(len(departments))
    ) as context:
        resp = user_drf_client.get(reverse("v2:departments_api-list"))
    duplicate_queries_check(context)
    empty_departments_data = resp.json()
    assert_drf_json_equal(
        empty_departments_data, empty_departments_from_fixture, ignore_order=True
    )

    courses, programs, _ = course_catalog_data
    for course in courses:
        course.departments.add(random.choice(departments))  # noqa: S311
    for program in programs:
        program.departments.add(random.choice(departments))  # noqa: S311
    with django_assert_max_num_queries(
        num_queries_from_department(len(departments))
    ) as context:
        resp = user_drf_client.get(reverse("v2:departments_api-list"))
    duplicate_queries_check(context)
    departments_data = resp.json()
    departments_from_fixture = []
    for department in departments:
        departments_from_fixture.append(  # noqa: PERF401
            DepartmentWithCoursesAndProgramsSerializer(
                instance=department, context=mock_context
            ).data
        )
    assert_drf_json_equal(departments_data, departments_from_fixture, ignore_order=True)


@pytest.mark.parametrize("course_catalog_course_count", [1], indirect=True)
@pytest.mark.parametrize("course_catalog_program_count", [1], indirect=True)
def test_get_program(
    user_drf_client, django_assert_max_num_queries, course_catalog_data
):
    """Test the view that handles a request for single Program"""
    _, programs, _ = course_catalog_data
    program = programs[0]
    num_queries = num_queries_from_programs([program], "v2")
    with django_assert_max_num_queries(num_queries) as context:
        resp = user_drf_client.get(
            reverse("v2:programs_api-detail", kwargs={"pk": program.id})
        )
    duplicate_queries_check(context)
    program_data = resp.json()
    assert_drf_json_equal(
        program_data, ProgramSerializer(program).data, ignore_order=True
    )


@pytest.mark.parametrize("course_catalog_course_count", [1], indirect=True)
@pytest.mark.parametrize("course_catalog_program_count", [1], indirect=True)
def test_create_program(
    user_drf_client, django_assert_max_num_queries, course_catalog_data
):
    """Test the view that handles a request to create a Program"""
    _, programs, _ = course_catalog_data
    program = programs[0]
    program_data = ProgramSerializer(program).data
    del program_data["id"]
    program_data["title"] = "New Program Title"
    request_url = reverse("v2:programs_api-list")
    with django_assert_max_num_queries(1) as context:
        resp = user_drf_client.post(request_url, program_data)
    duplicate_queries_check(context)
    assert resp.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


@pytest.mark.parametrize("course_catalog_course_count", [1], indirect=True)
@pytest.mark.parametrize("course_catalog_program_count", [1], indirect=True)
def test_patch_program(
    user_drf_client, django_assert_max_num_queries, course_catalog_data
):
    """Test the view that handles a request to patch a Program"""
    _, programs, _ = course_catalog_data
    program = programs[0]
    request_url = reverse("v2:programs_api-detail", kwargs={"pk": program.id})
    with django_assert_max_num_queries(1) as context:
        resp = user_drf_client.patch(request_url, {"title": "New Program Title"})
    duplicate_queries_check(context)
    assert resp.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


@pytest.mark.parametrize("course_catalog_course_count", [1], indirect=True)
@pytest.mark.parametrize("course_catalog_program_count", [1], indirect=True)
def test_delete_program(
    user_drf_client, django_assert_max_num_queries, course_catalog_data
):
    """Test the view that handles a request to delete a Program"""
    _, programs, _ = course_catalog_data
    program = programs[0]
    with django_assert_max_num_queries(1) as context:
        resp = user_drf_client.delete(
            reverse("v2:programs_api-detail", kwargs={"pk": program.id})
        )
    duplicate_queries_check(context)
    assert resp.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


@pytest.mark.skip_nplusone_check
@pytest.mark.usefixtures("course_catalog_data")
@pytest.mark.parametrize("course_catalog_course_count", [100], indirect=True)
@pytest.mark.parametrize("course_catalog_program_count", [12], indirect=True)
@pytest.mark.parametrize("include_finaid", [None, True, False])
@pytest.mark.parametrize("courserun_is_enrollable", [None, True, False])
def test_get_courses(
    user_drf_client,
    mock_context,
    django_assert_max_num_queries,
    include_finaid,
    courserun_is_enrollable,
):
    """Test the view that handles requests for all Courses"""
    courses_from_fixture = []
    num_queries = 2  # django_site + course count as a minimum
    params = {"page_size": 100}

    courses = Course.objects.order_by("title").prefetch_related("departments")

    if include_finaid is not None:
        mock_context["include_approved_financial_aid"] = include_finaid
        params["include_approved_financial_aid"] = include_finaid

    if courserun_is_enrollable is not None:
        params["courserun_is_enrollable"] = courserun_is_enrollable

        if courserun_is_enrollable:
            courses = get_enrollable_courses(courses)
        else:
            courses = get_unenrollable_courses(courses)

    for course in courses:
        courses_from_fixture.append(
            CourseWithCourseRunsSerializer(instance=course, context=mock_context).data
        )
        num_queries += num_queries_from_course(course, "v1")

    with django_assert_max_num_queries(num_queries) as context:
        query_count_start = len(connection.queries)
        resp = user_drf_client.get(reverse("v2:courses_api-list"), params)
        query_count_end = len(connection.queries)
        logger.info(
            f"test_get_course logged {query_count_end - query_count_start} queries"  # noqa: G004
        )
    #     This will become an assert rather than a warning in the future, for now this function is informational
    duplicate_queries_check(context)
    courses_data = resp.json()["results"]
    assert len(courses_data) == len(courses_from_fixture)
    """
    Due to the number of relations in our current course endpoint, and the potential for re-ordering of those nested
    objects, deepdiff has an ignore_order flag which I've added with an optional boolean argument to the assert_drf_json
    function.
    """
    assert_drf_json_equal(courses_data, courses_from_fixture, ignore_order=True)


@pytest.mark.parametrize("course_catalog_course_count", [1], indirect=True)
@pytest.mark.parametrize("course_catalog_program_count", [1], indirect=True)
@pytest.mark.parametrize("include_finaid", [True, False])
def test_get_course(
    user_drf_client,
    course_catalog_data,
    mock_context,
    django_assert_max_num_queries,
    include_finaid,
):
    """Test the view that handles a request for single Course"""
    courses, _, _ = course_catalog_data
    course = courses[0]
    num_queries = num_queries_from_course(course, "v2")

    if include_finaid:
        mock_context["include_approved_financial_aid"] = True

    with django_assert_max_num_queries(num_queries) as context:
        query_count_start = len(connection.queries)
        resp = user_drf_client.get(
            reverse("v2:courses_api-detail", kwargs={"pk": course.id}),
            {"include_approved_financial_aid": include_finaid},
        )
        query_count_end = len(connection.queries)
        logger.info(
            f"test_get_course logged {query_count_end - query_count_start} queries"  # noqa: G004
        )
    duplicate_queries_check(context)
    course_data = resp.json()
    course_from_fixture = dict(
        CourseWithCourseRunsSerializer(instance=course, context=mock_context).data
    )
    assert_drf_json_equal(course_data, course_from_fixture, ignore_order=True)


@pytest.mark.django_db
def test_get_course_with_readable_id_includes_programs(user_drf_client):
    """Test that requesting a course with readable_id query param includes programs in response"""
    # Create a course and a program that includes it
    course = CourseFactory.create()
    CourseRunFactory.create(course=course)

    program = ProgramFactory.create()
    program.add_requirement(course)
    program.refresh_from_db()

    # Request the course with readable_id query param
    resp = user_drf_client.get(
        reverse("v2:courses_api-detail", kwargs={"pk": course.id}),
        {"readable_id": course.readable_id},
    )

    assert resp.status_code == status.HTTP_200_OK
    course_data = resp.json()

    # Verify that programs are included in the response
    assert "programs" in course_data
    assert course_data["programs"] is not None
    assert len(course_data["programs"]) == 1
    assert course_data["programs"][0]["id"] == program.id
    assert course_data["programs"][0]["readable_id"] == program.readable_id
    assert course_data["programs"][0]["title"] == program.title


@pytest.mark.django_db
def test_get_course_without_readable_id_excludes_programs(user_drf_client):
    """Test that requesting a course without readable_id query param excludes programs from response"""
    # Create a course and a program that includes it
    course = CourseFactory.create()
    CourseRunFactory.create(course=course)

    program = ProgramFactory.create()
    program.add_requirement(course)
    program.refresh_from_db()

    # Request the course without readable_id query param
    resp = user_drf_client.get(
        reverse("v2:courses_api-detail", kwargs={"pk": course.id})
    )

    assert resp.status_code == status.HTTP_200_OK
    course_data = resp.json()

    # Verify that programs field is None when readable_id is not provided
    assert "programs" in course_data
    assert course_data["programs"] is None


@pytest.mark.django_db
def test_filter_with_org_id_anonymous():
    org = OrganizationPageFactory(name="Test Org")

    client = APIClient()

    unrelated_course = Course.objects.create(title="Other Course")
    CourseRunFactory(course=unrelated_course)

    url = reverse("v2:courses_api-list")
    response = client.get(url, {"org_id": org.id})

    assert response.data["results"] == []


@pytest.mark.django_db
@pytest.mark.skip_nplusone_check
def test_filter_with_org_id_returns_contracted_course(
    mocker, contract_ready_course, mock_course_run_clone
):
    org = OrganizationPageFactory(name="Test Org")
    contract = ContractPageFactory(organization=org, active=True)
    user = UserFactory()
    user.b2b_organizations.add(org)
    user.b2b_contracts.add(contract)
    user.refresh_from_db()

    (course, _) = contract_ready_course
    create_contract_run(contract, course)

    client = APIClient()
    client.force_authenticate(user=user)

    unrelated_course = Course.objects.create(title="Other Course")
    CourseRunFactory(course=unrelated_course)

    url = reverse("v2:courses_api-list")
    response = client.get(url, {"org_id": org.id})

    titles = [result["title"] for result in response.data["results"]]
    assert course.title in titles
    assert unrelated_course.title not in titles


@pytest.mark.django_db
@pytest.mark.skip_nplusone_check
def test_filter_with_org_id_user_not_associated_with_org_returns_no_courses(
    contract_ready_course, mock_course_run_clone
):
    org = OrganizationPageFactory(name="Test Org")
    user = UserFactory()
    contract = ContractPageFactory(organization=org, active=True)
    (course, _) = contract_ready_course
    create_contract_run(contract, course)

    client = APIClient()
    client.force_authenticate(user=user)

    unrelated_course = Course.objects.create(title="Other Course")
    CourseRunFactory(course=unrelated_course)

    url = reverse("v2:courses_api-list")
    response = client.get(url, {"org_id": org.id})

    titles = [result["title"] for result in response.data["results"]]
    assert course.title not in titles
    assert unrelated_course.title not in titles


@pytest.mark.django_db
@pytest.mark.skip_nplusone_check
def test_filter_with_org_id_multiple_courses_same_org(
    contract_ready_course, mock_course_run_clone
):
    """Test that filtering by org_id returns all contracted courses for that org"""
    org = OrganizationPageFactory(name="Test Org")
    contract = ContractPageFactory(organization=org, active=True)
    user = UserFactory()
    user.b2b_organizations.add(org)
    user.b2b_contracts.add(contract)
    user.refresh_from_db()

    # Create multiple courses for the same org
    (course1, _) = contract_ready_course
    create_contract_run(contract, course1)

    course2 = CourseFactory()
    CourseRunFactory(course=course2, is_source_run=True)
    create_contract_run(contract, course2)

    course3 = CourseFactory()
    CourseRunFactory(course=course3, is_source_run=True)
    create_contract_run(contract, course3)

    # Create unrelated course (no contract_run - should not appear in results)
    unrelated_course = CourseFactory()
    CourseRunFactory(course=unrelated_course)

    client = APIClient()
    client.force_authenticate(user=user)

    url = reverse("v2:courses_api-list")
    response = client.get(url, {"org_id": org.id})

    course_ids = [result["id"] for result in response.data["results"]]
    assert course1.id in course_ids
    assert course2.id in course_ids
    assert course3.id in course_ids
    assert unrelated_course.id not in course_ids
    assert len(course_ids) == 3


@pytest.mark.django_db
@pytest.mark.skip_nplusone_check
def test_filter_with_org_id_inactive_contract_excluded(
    contract_ready_course, mock_course_run_clone
):
    """Test that courses from inactive contracts are not returned"""
    org = OrganizationPageFactory(name="Test Org")
    contract = ContractPageFactory(organization=org, active=False)
    user = UserFactory()
    user.b2b_organizations.add(org)
    user.b2b_contracts.add(contract)
    user.refresh_from_db()

    (course, _) = contract_ready_course
    create_contract_run(contract, course)

    client = APIClient()
    client.force_authenticate(user=user)

    url = reverse("v2:courses_api-list")
    response = client.get(url, {"org_id": org.id})

    assert response.data["results"] == []


@pytest.mark.django_db
@pytest.mark.skip_nplusone_check
def test_filter_with_org_id_multiple_orgs(contract_ready_course, mock_course_run_clone):
    """Test that filtering by org_id returns courses only for that specific org"""
    org1 = OrganizationPageFactory(name="Test Org 1")
    org2 = OrganizationPageFactory(name="Test Org 2")
    contract1 = ContractPageFactory(organization=org1, active=True)
    contract2 = ContractPageFactory(organization=org2, active=True)

    user = UserFactory()
    user.b2b_organizations.add(org1, org2)
    user.b2b_contracts.add(contract1, contract2)
    user.refresh_from_db()

    (course1, _) = contract_ready_course
    create_contract_run(contract1, course1)

    course2 = CourseFactory()
    CourseRunFactory(course=course2, is_source_run=True)
    create_contract_run(contract2, course2)

    client = APIClient()
    client.force_authenticate(user=user)

    url = reverse("v2:courses_api-list")

    # Filter for org1
    response = client.get(url, {"org_id": org1.id})
    course_ids = [result["id"] for result in response.data["results"]]
    assert course1.id in course_ids
    assert course2.id not in course_ids

    # Filter for org2
    response = client.get(url, {"org_id": org2.id})
    course_ids = [result["id"] for result in response.data["results"]]
    assert course2.id in course_ids
    assert course1.id not in course_ids


@pytest.mark.django_db
@pytest.mark.skip_nplusone_check
def test_filter_with_org_id_user_in_org_but_no_contract(
    contract_ready_course, mock_course_run_clone
):
    """Test that user in org can see org's contracted courses"""
    org = OrganizationPageFactory(name="Test Org")
    contract = ContractPageFactory(organization=org, active=True)
    user = UserFactory()
    user.b2b_organizations.add(org)
    # User is in org but NOT added to contract
    user.refresh_from_db()

    (course, _) = contract_ready_course
    create_contract_run(contract, course)

    client = APIClient()
    client.force_authenticate(user=user)

    url = reverse("v2:courses_api-list")
    response = client.get(url, {"org_id": org.id})

    titles = [result["title"] for result in response.data["results"]]
    assert course.title in titles


@pytest.mark.django_db
def test_filter_with_org_id_nonexistent_org_id(user_drf_client):
    """Test that filtering with a nonexistent org_id returns no results"""
    course = CourseFactory(title="Test Course")
    CourseRunFactory(course=course)

    url = reverse("v2:courses_api-list")
    response = user_drf_client.get(url, {"org_id": 99999})

    assert response.data["results"] == []


@pytest.mark.django_db
@pytest.mark.skip_nplusone_check
def test_filter_with_org_id_returns_detail_view(
    contract_ready_course, mock_course_run_clone
):
    """Test that org_id filter works on detail view endpoint"""
    org = OrganizationPageFactory(name="Test Org")
    contract = ContractPageFactory(organization=org, active=True)
    user = UserFactory()
    user.b2b_organizations.add(org)
    user.b2b_contracts.add(contract)
    user.refresh_from_db()

    (course, _) = contract_ready_course
    create_contract_run(contract, course)

    client = APIClient()
    client.force_authenticate(user=user)

    url = reverse("v2:courses_api-detail", kwargs={"pk": course.id})
    response = client.get(url, {"org_id": org.id})

    assert response.status_code == status.HTTP_200_OK
    assert response.data["id"] == course.id
    assert response.data["title"] == course.title


@pytest.mark.django_db
@pytest.mark.skip_nplusone_check
def test_filter_with_org_id_detail_view_unauthorized_user(
    contract_ready_course, mock_course_run_clone
):
    """Test that org_id filter prevents unauthorized users from viewing contracted courses"""
    org = OrganizationPageFactory(name="Test Org")
    contract = ContractPageFactory(organization=org, active=True)
    user = UserFactory()
    # User NOT added to org
    user.refresh_from_db()

    (course, _) = contract_ready_course
    create_contract_run(contract, course)

    client = APIClient()
    client.force_authenticate(user=user)

    url = reverse("v2:courses_api-detail", kwargs={"pk": course.id})
    response = client.get(url, {"org_id": org.id})

    # User doesn't have access to this org, so should get 404
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
@pytest.mark.skip_nplusone_check
def test_filter_with_org_id_respects_course_live_status(
    contract_ready_course, mock_course_run_clone
):
    """Test that org_id filter returns contracted courses regardless of live status"""
    org = OrganizationPageFactory(name="Test Org")
    contract = ContractPageFactory(organization=org, active=True)
    user = UserFactory()
    user.b2b_organizations.add(org)
    user.b2b_contracts.add(contract)
    user.refresh_from_db()

    (course, _) = contract_ready_course
    create_contract_run(contract, course)

    # Make course page not live - org_id filter doesn't filter by live status
    course.page.live = False
    course.page.save()

    client = APIClient()
    client.force_authenticate(user=user)

    url = reverse("v2:courses_api-list")
    response = client.get(url, {"org_id": org.id})

    # Course should appear even though it's not live
    course_ids = [result["id"] for result in response.data["results"]]
    assert course.id in course_ids


@pytest.mark.django_db
@pytest.mark.skip_nplusone_check
def test_filter_with_org_id_pagination(contract_ready_course, mock_course_run_clone):
    """Test that org_id filter works correctly with pagination"""
    org = OrganizationPageFactory(name="Test Org")
    contract = ContractPageFactory(organization=org, active=True)
    user = UserFactory()
    user.b2b_organizations.add(org)
    user.b2b_contracts.add(contract)
    user.refresh_from_db()

    (course1, _) = contract_ready_course
    create_contract_run(contract, course1)

    # Create more courses to test pagination
    for i in range(15):
        course = CourseFactory(title=f"Org Course {i}")
        CourseRunFactory(course=course, is_source_run=True)
        create_contract_run(contract, course)

    client = APIClient()
    client.force_authenticate(user=user)

    url = reverse("v2:courses_api-list")
    response = client.get(url, {"org_id": org.id, "page_size": 5})

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] >= 15
    assert len(response.data["results"]) == 5
    assert "next" in response.data
    assert response.data["next"] is not None


@pytest.mark.django_db
@pytest.mark.skip_nplusone_check
def test_filter_with_org_id_combined_with_other_filters(
    contract_ready_course, mock_course_run_clone
):
    """Test that org_id filter can be combined with other filters"""
    org = OrganizationPageFactory(name="Test Org")
    contract = ContractPageFactory(organization=org, active=True)
    user = UserFactory()
    user.b2b_organizations.add(org)
    user.b2b_contracts.add(contract)
    user.refresh_from_db()

    (course1, _) = contract_ready_course
    create_contract_run(contract, course1)

    course2 = CourseFactory()
    CourseRunFactory(course=course2, is_source_run=True)
    create_contract_run(contract, course2)

    unrelated_course = CourseFactory()
    CourseRunFactory(course=unrelated_course)

    client = APIClient()
    client.force_authenticate(user=user)

    url = reverse("v2:courses_api-list")
    # Filter by org_id and specific course readable_id
    response = client.get(url, {"org_id": org.id, "readable_id": course1.readable_id})

    assert response.status_code == status.HTTP_200_OK
    course_ids = [result["id"] for result in response.data["results"]]
    assert course1.id in course_ids
    assert course2.id not in course_ids
    assert unrelated_course.id not in course_ids


@pytest.mark.django_db
@pytest.mark.skip_nplusone_check
def test_filter_without_org_id_authenticated_user(user_drf_client):
    course_with_contract = CourseFactory(title="Contract Course")
    contract = ContractPageFactory(active=True)
    CourseRunFactory(course=course_with_contract, b2b_contract=contract)

    course_no_contract = CourseFactory(title="No Contract Course")
    CourseRunFactory(course=course_no_contract, b2b_contract=None)

    url = reverse("v2:courses_api-list")
    response = user_drf_client.get(url)

    titles = [result["title"] for result in response.data["results"]]

    assert course_no_contract.title in titles
    assert course_with_contract.title in titles


@pytest.mark.django_db
def test_filter_by_org_id_with_contracted_user(
    contract_ready_course, mock_course_run_clone
):
    org = OrganizationPageFactory(name="Test Org")
    contract = ContractPageFactory(organization=org, active=True)
    user = UserFactory()
    user.b2b_contracts.add(contract)

    program_with_contract = ProgramFactory.create()
    (course, _) = contract_ready_course
    program_with_contract.add_requirement(course)
    program_with_contract.refresh_from_db()

    contract.add_program_courses(program_with_contract)

    # Unrelated program (should not be included)
    ProgramFactory()

    client = APIClient()
    client.force_authenticate(user=user)
    url = reverse("v2:programs_api-list")
    response = client.get(url, {"org_id": org.id})

    assert program_with_contract.title in [
        program["title"] for program in response.data["results"]
    ]


@pytest.mark.django_db
def test_filter_by_org_id_without_contract_access(
    contract_ready_course, mock_course_run_clone
):
    """Test that filtering by org_id does nothing if the user isn't in the org"""
    org = OrganizationPageFactory()
    user = UserFactory()

    program_with_contract = ProgramFactory()
    (course, _) = contract_ready_course
    contract = ContractPageFactory(active=True, organization=org)
    program_with_contract.add_requirement(course)
    program_with_contract.refresh_from_db()

    contract.add_program_courses(program_with_contract)

    # Another program without contract (should be included)
    public_program = ProgramFactory()

    request = Request(RequestFactory().get("v2:programs_api-list", {"org_id": org.id}))
    request.user = user  # Not associated with org

    filterset = ProgramFilterSet(
        data={"org_id": org.id},
        queryset=Program.objects.all(),
        request=request,
    )

    filtered = filterset.qs
    assert public_program in filtered
    assert program_with_contract in filtered
    assert filtered.count() == 2


@pytest.mark.django_db
def test_filter_by_org_id_unauthenticated_user(
    contract_ready_course, mock_course_run_clone
):
    """Test that filtering by org_id does nothing if the user is unauthenticated"""
    org = OrganizationPageFactory()

    program_with_contract = ProgramFactory()
    (course, _) = contract_ready_course
    contract = ContractPageFactory(active=True, organization=org)

    program_with_contract.add_requirement(course)
    program_with_contract.refresh_from_db()

    contract.add_program_courses(program_with_contract)

    public_program = ProgramFactory()

    request = Request(RequestFactory().get("v2:programs_api-list", {"org_id": org.id}))
    request.user = AnonymousUser()

    filterset = ProgramFilterSet(
        data={"org_id": org.id},
        queryset=Program.objects.all(),
        request=request,
    )

    filtered = filterset.qs
    assert public_program in filtered
    assert program_with_contract in filtered
    assert filtered.count() == 2


@pytest.mark.django_db
def test_next_run_id_with_org_filter(  # noqa: PLR0915
    mock_course_run_clone,
    contract_ready_course,
):
    """
    Test that next_run_id returns the correct value according to the org filter.

    If the org filter is not specified, we should get a next_run_id that only
    considers non-B2B course runs.
    If the org filter _is_ specified, we should get the next valid run for the
    current user.
    """

    api_client = APIClient()
    orgs = []

    org = OrganizationPageFactory.create()
    org.org_key = "Org1"
    org.name = "Test Org 1"
    org.save()
    orgs.append(org)
    org = OrganizationPageFactory.create()
    org.org_key = "Org2"
    org.name = "Test Org 2"
    org.save()
    orgs.append(org)

    contract = ContractPageFactory.create(organization=orgs[0])
    second_contract = ContractPageFactory.create(organization=orgs[1])
    third_contract_first_org = ContractPageFactory.create(organization=orgs[0])
    test_user = UserFactory()
    test_user.b2b_organizations.add(contract.organization)
    test_user.b2b_contracts.add(contract)
    test_user.save()
    test_user.refresh_from_db()
    auth_api_client = APIClient()
    auth_api_client.force_authenticate(user=test_user)

    one_month_prior = now_in_utc() - timedelta(days=31)
    one_month_ahead = now_in_utc() + timedelta(days=31)

    b2b_course, _ = contract_ready_course
    regular_course_run = CourseRunFactory(
        start_date=one_month_prior,
        enrollment_start=one_month_prior,
        course=b2b_course,
    )

    # make the B2B run start a day further away from now than the regular run
    # if this weren't a B2B run, then that would give it precedence
    b2b_run, _ = create_contract_run(contract, b2b_course)
    b2b_run.start_date = one_month_prior - timedelta(days=1)
    b2b_run.enrollment_start = one_month_prior - timedelta(days=1)
    b2b_run.save()

    # first, test to make sure we get the regular run's ID
    resp = api_client.get(
        reverse("v2:courses_api-detail", kwargs={"pk": b2b_course.id}),
    )

    assert resp.status_code < 300
    resp_course = resp.json()
    assert resp_course["next_run_id"] == regular_course_run.id

    # if the regular run is in the future, we shouldn't get anything
    regular_course_run.enrollment_start = one_month_ahead
    regular_course_run.save()

    resp = api_client.get(
        reverse("v2:courses_api-detail", kwargs={"pk": b2b_course.id}),
    )

    assert resp.status_code < 300
    resp_course = resp.json()
    assert not resp_course["next_run_id"]
    assert b2b_run.enrollment_start < regular_course_run.enrollment_start

    # now, test with the org filter
    # we should get the B2B run
    url = reverse(
        "v2:courses_api-detail",
        kwargs={"pk": b2b_course.id},
    )

    resp = auth_api_client.get(f"{url}?org_id={contract.organization.id}")

    assert resp.status_code < 300
    resp_course = resp.json()
    assert resp_course["next_run_id"] == b2b_run.id

    # kick the B2B run into the future and now we should get nothing again
    b2b_run.enrollment_start = one_month_ahead
    b2b_run.save()

    resp = auth_api_client.get(f"{url}?org_id={contract.organization.id}")

    assert resp.status_code < 300
    resp_course = resp.json()
    assert not resp_course["next_run_id"]

    # put the first run's date back
    b2b_run.start_date = one_month_prior - timedelta(days=1)
    b2b_run.enrollment_start = one_month_prior - timedelta(days=1)
    b2b_run.save()

    # create a run for the other org, same course, and starting before b2b_run
    second_eligible_b2b_run = CourseRunFactory.create(
        b2b_contract=third_contract_first_org,
        start_date=one_month_prior - timedelta(days=5),
        enrollment_start=one_month_prior - timedelta(days=5),
        course=b2b_run.course,
    )

    # we're not in this contract so we should get the b2b_run id next
    resp = auth_api_client.get(f"{url}?org_id={contract.organization.id}")

    assert resp.status_code < 300
    resp_course = resp.json()
    assert resp_course["next_run_id"] == b2b_run.id

    # add to the other contract
    test_user.b2b_contracts.add(third_contract_first_org)
    test_user.save()

    # we should now get the second eligible run - our user is in both contracts
    resp = auth_api_client.get(f"{url}?org_id={contract.organization.id}")

    assert resp.status_code < 300
    resp_course = resp.json()
    assert resp_course["next_run_id"] == second_eligible_b2b_run.id

    # same test as above, but filter on contract ID

    url = reverse(
        "v2:courses_api-detail",
        kwargs={"pk": b2b_course.id},
    )

    resp = auth_api_client.get(f"{url}?contract_id={contract.id}")

    assert resp.status_code < 300
    resp_course = resp.json()
    assert resp_course["next_run_id"] == b2b_run.id

    # kick the B2B run into the future and now we should get nothing again
    b2b_run.enrollment_start = one_month_ahead
    b2b_run.save()

    resp = auth_api_client.get(f"{url}?contract_id={contract.id}")

    assert resp.status_code < 300
    resp_course = resp.json()
    assert not resp_course["next_run_id"]

    # finally, make a new contract and don't assign the user to it.
    # we should get a 404, since we're filtering on an org we're not in.

    second_b2b_run, _ = create_contract_run(second_contract, b2b_course)
    second_b2b_run.enrollment_start = one_month_prior
    second_b2b_run.save()

    resp = auth_api_client.get(f"{url}?org_id={second_contract.organization.id}")

    assert resp.status_code == 404


@pytest.mark.skip_nplusone_check
def test_user_enrollments_b2b_organization_filter(user_drf_client, user):
    """Test that user enrollments can be filtered by B2B organization ID"""

    org = OrganizationPageFactory.create()
    contract = ContractPageFactory.create(organization=org)

    regular_course = CourseFactory.create()
    regular_run = CourseRunFactory.create(course=regular_course)

    b2b_course = CourseFactory.create()
    b2b_run = CourseRunFactory.create(course=b2b_course, b2b_contract=contract)

    CourseRunEnrollmentFactory.create(user=user, run=regular_run)
    b2b_enrollment = CourseRunEnrollmentFactory.create(user=user, run=b2b_run)

    resp = user_drf_client.get(reverse("v2:user-enrollments-api-list"))
    assert resp.status_code == status.HTTP_200_OK
    assert len(resp.json()) == 2

    resp = user_drf_client.get(
        reverse("v2:user-enrollments-api-list"), {"org_id": org.id}
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == b2b_enrollment.id
    assert data[0]["b2b_organization_id"] == org.id
    assert data[0]["b2b_contract_id"] == contract.id

    resp = user_drf_client.get(
        reverse("v2:user-enrollments-api-list"), {"org_id": 99999}
    )
    assert resp.status_code == status.HTTP_200_OK
    assert len(resp.json()) == 0


def test_program_filter_for_b2b_org(user, mock_course_run_clone):
    """Test that filtering programs by org works as expected."""

    org = OrganizationPageFactory.create()
    contract = ContractPageFactory.create(organization=org)

    regular_program = ProgramFactory.create()
    b2b_program = ProgramFactory.create(b2b_only=True)

    regular_course = CourseFactory.create()
    CourseRunFactory.create(course=regular_course)
    regular_program.add_requirement(regular_course)
    regular_program.save()

    b2b_course = CourseFactory.create()
    CourseRunFactory.create(course=b2b_course, is_source_run=True)
    b2b_program.add_requirement(b2b_course)
    b2b_program.add_requirement(regular_course)
    b2b_program.b2b_only = True
    b2b_program.save()

    contract.add_program_courses(b2b_program)
    contract.save()

    user.b2b_organizations.add(org)
    user.b2b_contracts.add(contract)
    user.save()

    client = APIClient()
    client.force_authenticate(user=user)

    resp = client.get(reverse("v2:programs_api-list"))
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["count"] == 1
    assert data["results"][0]["id"] == regular_program.id

    resp = client.get(reverse("v2:programs_api-list"), data={"org_id": org.id})
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["count"] == 1
    assert data["results"][0]["id"] == b2b_program.id

    resp = client.get(reverse("v2:programs_api-detail", kwargs={"pk": b2b_program.id}))
    assert resp.status_code == status.HTTP_404_NOT_FOUND

    resp = client.get(
        reverse("v2:programs_api-detail", kwargs={"pk": b2b_program.id}),
        data={"org_id": org.id},
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["id"] == b2b_program.id


def test_program_filter_multiple_ids(user_drf_client):
    """Test that filtering programs by multiple IDs works as expected."""
    # Create several programs
    program1 = ProgramFactory.create(title="Program 1")
    program2 = ProgramFactory.create(title="Program 2")
    program3 = ProgramFactory.create(title="Program 3")
    program4 = ProgramFactory.create(title="Program 4")

    # Test fetching multiple programs by IDs
    resp = user_drf_client.get(
        reverse("v2:programs_api-list"),
        data={"id": f"{program1.id},{program3.id},{program4.id}"},
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["count"] == 3

    # Extract IDs from response
    returned_ids = [result["id"] for result in data["results"]]

    # Verify that only the requested programs are returned
    assert program1.id in returned_ids
    assert program2.id not in returned_ids
    assert program3.id in returned_ids
    assert program4.id in returned_ids

    # Test with single ID (should still work)
    resp = user_drf_client.get(
        reverse("v2:programs_api-list"), data={"id": str(program2.id)}
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["count"] == 1
    assert data["results"][0]["id"] == program2.id

    # Test with non-existent ID
    resp = user_drf_client.get(reverse("v2:programs_api-list"), data={"id": "99999"})
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["count"] == 0


def test_get_course_certificate():
    """
    Test that the get_course_certificate handles valid, invalid, and not-found
    """
    courseware_page = CoursePageFactory.create()
    cert_page = courseware_page.certificate_page
    cert_page.save_revision()  # we need at least one
    certificate = CourseRunCertificateFactory.create(
        certificate_page_revision=cert_page.revisions.last()
    )

    client = APIClient()
    resp = client.get(reverse("v2:get_course_certificate", args=[certificate.uuid]))
    assert resp.status_code == status.HTTP_200_OK
    assert resp.data == CourseRunCertificateSerializer(certificate).data

    resp404 = client.get(reverse("v2:get_course_certificate", args=[uuid.uuid4()]))
    assert resp404.status_code == status.HTTP_404_NOT_FOUND

    resp400 = client.get(reverse("v2:get_course_certificate", args=["not-uuid"]))
    assert resp400.status_code == status.HTTP_400_BAD_REQUEST


def test_get_program_certificate():
    """
    Test that the get_course_certificate handles valid, invalid, and not-found
    """
    courseware_page = ProgramPageFactory.create()
    cert_page = courseware_page.certificate_page
    cert_page.save_revision()  # we need at least one
    certificate = ProgramCertificateFactory.create(
        certificate_page_revision=cert_page.revisions.last()
    )

    client = APIClient()
    resp = client.get(reverse("v2:get_program_certificate", args=[certificate.uuid]))
    assert resp.status_code == status.HTTP_200_OK
    assert resp.data == ProgramCertificateSerializer(certificate).data

    resp404 = client.get(reverse("v2:get_program_certificate", args=[uuid.uuid4()]))
    assert resp404.status_code == status.HTTP_404_NOT_FOUND

    resp400 = client.get(reverse("v2:get_program_certificate", args=["not-uuid"]))
    assert resp400.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_filter_by_contract_id_with_contracted_user(
    contract_ready_course, mock_course_run_clone
):
    """Test that filtering by contract_id returns only programs in that contract for authorized users"""
    org = OrganizationPageFactory(name="Test Org")
    contract = ContractPageFactory(organization=org, active=True)
    user = UserFactory()
    user.b2b_contracts.add(contract)

    program_with_contract = ProgramFactory.create()
    (course, _) = contract_ready_course
    program_with_contract.add_requirement(course)
    program_with_contract.refresh_from_db()

    contract.add_program_courses(program_with_contract)

    # Unrelated program (should not be included)
    ProgramFactory()

    client = APIClient()
    client.force_authenticate(user=user)
    url = reverse("v2:programs_api-list")
    response = client.get(url, {"contract_id": contract.id})

    assert program_with_contract.title in [
        program["title"] for program in response.data["results"]
    ]


@pytest.mark.django_db
def test_filter_by_contract_id_without_contract_access(
    contract_ready_course, mock_course_run_clone
):
    """Test that filtering by contract_id returns only non-B2B programs if user doesn't have access"""
    org = OrganizationPageFactory()
    user = UserFactory()

    program_with_contract = ProgramFactory()
    (course, _) = contract_ready_course
    contract = ContractPageFactory(active=True, organization=org)
    program_with_contract.add_requirement(course)
    program_with_contract.refresh_from_db()

    contract.add_program_courses(program_with_contract)

    # Another program without contract (should be included)
    public_program = ProgramFactory()

    request = Request(
        RequestFactory().get("v2:programs_api-list", {"contract_id": contract.id})
    )
    request.user = user  # Not associated with contract

    filterset = ProgramFilterSet(
        data={"contract_id": contract.id},
        queryset=Program.objects.all(),
        request=request,
    )

    filtered = filterset.qs
    assert public_program in filtered
    assert program_with_contract in filtered
    assert filtered.count() == 2


@pytest.mark.django_db
def test_filter_by_contract_id_unauthenticated_user(
    contract_ready_course, mock_course_run_clone
):
    """Test that filtering by contract_id returns only non-B2B programs if user is unauthenticated"""
    org = OrganizationPageFactory()

    program_with_contract = ProgramFactory()
    (course, _) = contract_ready_course
    contract = ContractPageFactory(active=True, organization=org)

    program_with_contract.add_requirement(course)
    program_with_contract.refresh_from_db()

    contract.add_program_courses(program_with_contract)

    public_program = ProgramFactory()

    request = Request(
        RequestFactory().get("v2:programs_api-list", {"contract_id": contract.id})
    )
    request.user = AnonymousUser()

    filterset = ProgramFilterSet(
        data={"contract_id": contract.id},
        queryset=Program.objects.all(),
        request=request,
    )

    filtered = filterset.qs
    assert public_program in filtered
    assert program_with_contract in filtered
    assert filtered.count() == 2


@pytest.mark.django_db
def test_filter_courses_with_contract_id_authenticated_user(
    mocker, contract_ready_course, mock_course_run_clone
):
    """Test that filtering courses by contract_id returns contracted courses for authorized users"""
    org = OrganizationPageFactory(name="Test Org")
    contract = ContractPageFactory(organization=org, active=True)
    user = UserFactory()
    user.b2b_contracts.add(contract)
    user.refresh_from_db()

    (course, _) = contract_ready_course
    create_contract_run(contract, course)

    client = APIClient()
    client.force_authenticate(user=user)

    unrelated_course = Course.objects.create(title="Other Course")
    CourseRunFactory(course=unrelated_course)

    url = reverse("v2:courses_api-list")
    response = client.get(url, {"contract_id": contract.id})

    titles = [result["title"] for result in response.data["results"]]
    assert course.title in titles
    assert unrelated_course.title not in titles

    # Test that the contract runs are filtered according to the contract ID as well

    other_contract = ContractPageFactory(organization=org, active=True)
    unrelated_course_run = CourseRunFactory(course=course, b2b_contract=other_contract)

    url = reverse("v2:courses_api-list")
    response = client.get(url, {"contract_id": contract.id})

    test_course_runs = [
        (
            (
                run["courseware_id"]
                for run in test_course["courseruns"]
                if test_course["id"] == course.id
            )
            for test_course in response.data["results"]
        )
    ]

    assert unrelated_course_run.courseware_id not in test_course_runs


@pytest.mark.django_db
def test_filter_courses_with_contract_id_no_access(
    contract_ready_course, mock_course_run_clone
):
    """Test that filtering courses by contract_id returns no courses if user lacks access"""
    org = OrganizationPageFactory(name="Test Org")
    user = UserFactory()
    contract = ContractPageFactory(organization=org, active=True)
    (course, _) = contract_ready_course
    create_contract_run(contract, course)

    client = APIClient()
    client.force_authenticate(user=user)

    unrelated_course = Course.objects.create(title="Other Course")
    CourseRunFactory(course=unrelated_course)

    url = reverse("v2:courses_api-list")
    response = client.get(url, {"contract_id": contract.id})

    assert response.data["results"] == []


@pytest.mark.django_db
def test_filter_courses_with_contract_id_anonymous():
    """Test that filtering courses by contract_id returns no courses for anonymous users"""
    org = OrganizationPageFactory(name="Test Org")
    contract = ContractPageFactory(organization=org, active=True)

    client = APIClient()

    unrelated_course = Course.objects.create(title="Other Course")
    CourseRunFactory(course=unrelated_course)

    url = reverse("v2:courses_api-list")
    response = client.get(url, {"contract_id": contract.id})

    assert response.data["results"] == []


@pytest.mark.skip_nplusone_check
@pytest.mark.usefixtures("b2b_courses")
def test_program_enrollments(user_drf_client, user_with_enrollments_and_certificates):
    """
    Tests the program enrollments API, which should show the user's enrollment
    in programs with the course runs that apply.
    """
    user = user_with_enrollments_and_certificates

    program_enrollments = (
        ProgramEnrollment.objects.filter(user=user)
        .filter(~Q(change_status=ENROLL_CHANGE_STATUS_UNENROLLED))
        .order_by("-id")
    )

    courses_by_program_id = {
        program_enrollment.program_id: Course.objects.filter(
            in_programs__program=program_enrollment.program
        ).order_by("in_programs__path")
        for program_enrollment in program_enrollments
    }

    run_enrollments_by_program_id = {
        program_enrollment.program_id: CourseRunEnrollment.objects.filter(
            user=user, run__course__in_programs__program=program_enrollment.program
        )
        .filter(~Q(change_status=ENROLL_CHANGE_STATUS_UNENROLLED))
        .order_by("-id")
        for program_enrollment in program_enrollments
    }

    # assert that we ended up with data
    assert len(program_enrollments) > 0
    for runs in run_enrollments_by_program_id.values():
        assert len(runs) > 0

    resp = user_drf_client.get(reverse("v2:user_program_enrollments_api-list"))

    assert resp.status_code == status.HTTP_200_OK

    def _get_page_prop(program_enrollment, prop, default=None):
        program = program_enrollment.program
        if hasattr(program, "page") and hasattr(program.page, prop):
            return getattr(program.page, prop, default)
        return default

    assert resp.json() == [
        {
            "program": {
                "id": program_enrollment.program.id,
                "title": program_enrollment.program.title,
                "live": program_enrollment.program.live,
                "departments": [],
                "readable_id": program_enrollment.program.readable_id,
                "req_tree": list(
                    ProgramRequirementTreeSerializer(
                        program_enrollment.program.get_requirements_root()
                    ).data
                ),
                "collections": [],
                "availability": "anytime",
                "certificate_type": "Certificate of Completion",
                "required_prerequisites": _get_page_prop(
                    program_enrollment, "prerequisites", ""
                )
                != "",
                "topics": [],
                "start_date": ANY_STR,
                "end_date": None,
                "enrollment_end": None,
                "enrollment_start": None,
                "duration": _get_page_prop(program_enrollment, "length"),
                "time_commitment": _get_page_prop(program_enrollment, "effort"),
                "min_price": _get_page_prop(program_enrollment, "min_price"),
                "max_price": _get_page_prop(program_enrollment, "max_price"),
                "min_weeks": _get_page_prop(program_enrollment, "min_weeks"),
                "max_weeks": _get_page_prop(program_enrollment, "max_weeks"),
                "min_weekly_hours": _get_page_prop(
                    program_enrollment, "min_weekly_hours"
                ),
                "max_weekly_hours": _get_page_prop(
                    program_enrollment, "max_weekly_hours"
                ),
                "requirements": {
                    "courses": {
                        "electives": [
                            {"id": course.id, "readable_id": course.readable_id}
                            for course in program_enrollment.program.elective_courses
                        ],
                        "required": [
                            {"id": course.id, "readable_id": course.readable_id}
                            for course in program_enrollment.program.required_courses
                        ],
                    },
                    "programs": {
                        "electives": [
                            {"id": program.id, "readable_id": program.readable_id}
                            for program in program_enrollment.program.elective_programs
                        ],
                        "required": [
                            {"id": program.id, "readable_id": program.readable_id}
                            for program in program_enrollment.program.required_programs
                        ],
                    },
                },
                "program_type": program_enrollment.program.program_type,
                "page": dict(
                    ProgramPageSerializer(program_enrollment.program.page).data
                ),
                "courses": [
                    course.id
                    for course in courses_by_program_id[program_enrollment.program.id]
                ],
            },
            "certificate": maybe_serialize_program_cert(
                program_enrollment.program, user
            ),
            "enrollments": [
                {
                    "approved_flexible_price_exists": False,
                    "edx_emails_subscription": True,
                    "certificate": maybe_serialize_course_cert(
                        run_enrollment.run, user
                    ),
                    "grades": [],
                    "id": run_enrollment.id,
                    "enrollment_mode": run_enrollment.enrollment_mode,
                    "run": dict(CourseRunWithCourseSerializer(run_enrollment.run).data),
                    **(
                        {
                            "b2b_contract_id": run_enrollment.run.b2b_contract.id,
                            "b2b_organization_id": run_enrollment.run.b2b_contract.organization_id,
                        }
                        if run_enrollment.run.b2b_contract
                        else {
                            "b2b_contract_id": None,
                            "b2b_organization_id": None,
                        }
                    ),
                }
                for run_enrollment in run_enrollments_by_program_id[
                    program_enrollment.program_id
                ]
            ],
        }
        for program_enrollment in program_enrollments
    ]


@pytest.mark.skip_nplusone_check
@responses.activate
@pytest.mark.parametrize(
    (
        "program_enrollment_type",
        "requirement_type",
    ),
    [
        (
            None,
            "requirement",
        ),
        (
            EDX_ENROLLMENT_AUDIT_MODE,
            "requirement",
        ),
        (
            EDX_ENROLLMENT_VERIFIED_MODE,
            "requirement",
        ),
        (
            EDX_ENROLLMENT_AUDIT_MODE,
            "elective",
        ),
        (
            EDX_ENROLLMENT_VERIFIED_MODE,
            "elective",
        ),
        (
            EDX_ENROLLMENT_AUDIT_MODE,
            "elective-extra",
        ),
        (
            EDX_ENROLLMENT_VERIFIED_MODE,
            "elective-extra",
        ),
    ],
)
def test_add_verified_program_course_enrollment(
    user, user_drf_client, program_enrollment_type, requirement_type
):
    """
    Test that the endpoint works as expected.

    The codepath for creating the verified enrollments has its own tests, so
    this is testing the setup and check processes.
    """

    responses.add(
        responses.GET,
        f"{settings.OPENEDX_API_BASE_URL}/api/enrollment/v1/enrollments",
        json={
            "results": [
                {"mode": program_enrollment_type, "is_active": True},
            ],
        },
        status=status.HTTP_200_OK,
    )

    if program_enrollment_type:
        prog_enrollment = ProgramEnrollmentFactory.create(
            user=user, enrollment_mode=program_enrollment_type
        )
        program = prog_enrollment.program

        if program_enrollment_type == EDX_ENROLLMENT_VERIFIED_MODE:
            program_content_type = ContentType.objects.get_for_model(program)
            with reversion.create_revision():
                Product.objects.create(
                    price=10,
                    is_active=True,
                    object_id=program.id,
                    content_type=program_content_type,
                )
    else:
        program = ProgramFactory.create()

    course_run = CourseRunFactory.create()
    program.add_requirement(
        course_run.course
    ) if requirement_type == "requirement" else program.add_elective(course_run.course)

    if program_enrollment_type == EDX_ENROLLMENT_VERIFIED_MODE:
        course_run_content_type = ContentType.objects.get_for_model(course_run)
        with reversion.create_revision():
            Product.objects.create(
                price=10,
                is_active=True,
                object_id=course_run.id,
                content_type=course_run_content_type,
            )

    if requirement_type == "elective-extra":
        # Add another elective, adjust the requirement to only require one, and
        # give the user a verified enrollment in that course. This should result
        # in the learner getting an _audit_ enrollment in the course created
        # earlier.
        second_elective = CourseRunFactory.create()
        program.add_elective(second_elective.course)
        CourseRunEnrollmentFactory.create(
            user=user,
            run=second_elective,
            active=True,
            enrollment_mode=EDX_ENROLLMENT_VERIFIED_MODE,
        )

    resp = user_drf_client.post(
        reverse(
            "v2:add_verified_program_course_enrollment",
            kwargs={
                "courserun_id": course_run.courseware_id,
                "program_id": program.readable_id,
            },
        )
    )

    if program_enrollment_type:
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.json()["run"]["id"] == course_run.id

        if (
            program_enrollment_type == EDX_ENROLLMENT_VERIFIED_MODE
            and requirement_type != "elective-extra"
        ):
            order = user.orders.last()
            line = order.lines.last()
            assert course_run == line.purchased_object
            assert resp.json()["enrollment_mode"] == EDX_ENROLLMENT_VERIFIED_MODE

        if (
            program_enrollment_type == EDX_ENROLLMENT_VERIFIED_MODE
            and requirement_type == "elective-extra"
        ):
            # We had enough electives so we should have gotten an audit enrollment
            assert resp.json()["enrollment_mode"] == EDX_ENROLLMENT_AUDIT_MODE


@pytest.mark.skip_nplusone_check
@pytest.mark.parametrize(
    "sync_on_load,flag_enabled,sync_raises",  # noqa: PT006
    [
        (False, False, False),  # Sync disabled -> no sync, no error
        (True, False, False),  # Sync enabled, flag disabled, no error -> no error
        (True, True, False),  # Sync enabled, flag enabled, no error -> no error
        (True, True, True),  # Sync enabled, flag enabled, error -> no error (logged)
    ],
)
def test_user_enrollments_list_sync_with_flag(  # noqa: PLR0913
    mocker,
    user_drf_client,
    user,
    sync_on_load,
    flag_enabled,
    sync_raises,
):
    """
    Test that UserEnrollmentsApiViewSet.list() respects IGNORE_EDX_FAILURES flag
    when syncing enrollments with edX.
    """

    # Create a test enrollment
    CourseRunEnrollmentFactory.create(user=user)

    # Mock the SYNC_ON_DASHBOARD_LOAD flag
    mocker.patch(
        "courses.views.v2.is_enabled",
        side_effect=lambda flag: (
            sync_on_load if flag == features.SYNC_ON_DASHBOARD_LOAD else False
        ),
    )

    # Mock the FEATURES dict for IGNORE_EDX_FAILURES
    mocker.patch.dict(
        settings.FEATURES,
        {"IGNORE_EDX_FAILURES": flag_enabled},
    )

    # Mock sync_enrollments_with_edx
    sync_mock = mocker.patch("courses.views.v2.sync_enrollments_with_edx")
    if sync_raises:
        sync_mock.side_effect = Exception("Sync failure")

    mocker.patch("courses.views.v2.log.exception")

    # When flag is enabled or sync succeeds, expect 200
    resp = user_drf_client.get(reverse("v2:user-enrollments-api-list"))
    assert resp.status_code == status.HTTP_200_OK
    # Verify sync was called or not called based on sync_on_load
    if sync_on_load:
        sync_mock.assert_called_once_with(user)
    else:
        sync_mock.assert_not_called()


@pytest.mark.skip_nplusone_check
@pytest.mark.parametrize(
    "with_b2b",
    [
        True,
        False,
    ],
)
@pytest.mark.parametrize(
    "single",
    [
        True,
        False,
    ],
)
def test_get_courses_b2b_runs(with_b2b, single, user_drf_client):
    """
    Test that the courses API returns courses with or without b2b runs.

    By default courses should only have runs that aren't B2B runs. There are
    other tests that test the result if you've specified an org/etc. so this
    doesn't test that.
    """

    contract = ContractPageFactory.create() if with_b2b else None

    test_course_run = CourseRunFactory.create(b2b_contract=contract)

    url = reverse("v2:courses_api-list")
    response_raw = user_drf_client.get(
        url,
        query_params=(
            {"readable_id": test_course_run.course.readable_id} if single else {}
        ),
    )
    assert response_raw.status_code < 300
    response = response_raw.json()["results"]

    assert len(response) == 1
    returned_course = response[0]

    assert returned_course["readable_id"] == test_course_run.course.readable_id

    if with_b2b:
        assert len(returned_course["courseruns"]) == 0
    else:
        assert len(returned_course["courseruns"]) == 1
        assert (
            returned_course["courseruns"][0]["courseware_id"]
            == test_course_run.courseware_id
        )


@pytest.mark.skip_nplusone_check
@pytest.mark.parametrize(
    "with_b2b",
    [
        True,
        False,
    ],
)
def test_get_courses_b2b_programs(with_b2b, user_drf_client):
    """
    Test that the courses API returns courses with or without b2b programs.

    By default courses should only list programs that aren't marked as b2b_only.
    Again, other tests handle filtering of that list so not testing that here.
    """

    program = ProgramFactory.create(b2b_only=with_b2b)

    test_course_run = CourseRunFactory.create()
    program.add_requirement(test_course_run.course)

    url = reverse("v2:courses_api-list")
    response_raw = user_drf_client.get(
        url,
        query_params={"readable_id": test_course_run.course.readable_id},
    )
    assert response_raw.status_code < 300
    response = response_raw.json()["results"]

    assert len(response) == 1
    returned_course = response[0]

    assert returned_course["readable_id"] == test_course_run.course.readable_id

    if with_b2b:
        assert len(returned_course["programs"]) == 0
    else:
        assert len(returned_course["programs"]) == 1
        assert returned_course["programs"][0]["readable_id"] == program.readable_id


def test_get_courses_with_specified_contract_programs(user, user_drf_client):
    """
    Test that specifying a contract when retrieving a course returns only
    applicable B2B programs.

    This is different than testing for the b2b flag alone - if we have a
    contract ID specified, then the programs in the list should only be ones
    attached to that contract.
    """

    contract = ContractPageFactory.create()
    user.b2b_contracts.add(contract)
    other_contract = ContractPageFactory.create()

    programs = ProgramFactory.create_batch(2)
    course_run = CourseRunFactory.create(b2b_contract=contract)
    CourseRunFactory.create(b2b_contract=other_contract, course=course_run.course)

    for program in programs:
        program.add_requirement(course_run.course)
        program.save()

    ContractProgramItem.objects.create(contract=contract, program=programs[0])

    url = reverse("v2:courses_api-list")
    response_raw = user_drf_client.get(
        url,
        query_params={
            "readable_id": course_run.course.readable_id,
            "contract_id": contract.id,
        },
    )
    assert response_raw.status_code < 300
    response = response_raw.json()["results"]

    assert len(response[0]["programs"]) > 0

    program_ids = [program["id"] for program in response[0]["programs"]]
    assert programs[0].id in program_ids
    assert programs[1].id not in program_ids
