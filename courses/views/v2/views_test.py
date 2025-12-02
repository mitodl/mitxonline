"""
Tests for courses api views v2
"""

import logging
import random
import uuid
from datetime import timedelta

import pytest
from django.contrib.auth.models import AnonymousUser
from django.db import connection
from django.test.client import RequestFactory
from django.urls import reverse
from faker import Faker
from mitol.common.utils import now_in_utc
from rest_framework import status
from rest_framework.request import Request
from rest_framework.test import APIClient

from b2b.api import create_contract_run
from b2b.factories import ContractPageFactory, OrganizationPageFactory
from cms.factories import CoursePageFactory, ProgramPageFactory
from courses.factories import (
    CourseFactory,
    CourseRunCertificateFactory,
    CourseRunEnrollmentFactory,
    CourseRunFactory,
    DepartmentFactory,
    ProgramCertificateFactory,
    ProgramFactory,
)
from courses.models import Course, Program
from courses.serializers.v2.certificates import (
    CourseRunCertificateSerializer,
    ProgramCertificateSerializer,
)
from courses.serializers.v2.courses import CourseWithCourseRunsSerializer
from courses.serializers.v2.departments import (
    DepartmentWithCoursesAndProgramsSerializer,
)
from courses.serializers.v2.programs import ProgramSerializer
from courses.utils import get_enrollable_courses, get_unenrollable_courses
from courses.views.test_utils import (
    num_queries_from_course,
    num_queries_from_department,
    num_queries_from_programs,
)
from courses.views.v2 import Pagination, ProgramFilterSet
from main.test_utils import assert_drf_json_equal, duplicate_queries_check
from users.factories import UserFactory

pytestmark = [pytest.mark.django_db]
logger = logging.getLogger(__name__)
faker = Faker()


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
def test_filter_with_org_id_anonymous():
    org = OrganizationPageFactory(name="Test Org")

    client = APIClient()

    unrelated_course = Course.objects.create(title="Other Course")
    CourseRunFactory(course=unrelated_course)

    url = reverse("v2:courses_api-list")
    response = client.get(url, {"org_id": org.id})

    assert response.data["results"] == []


@pytest.mark.django_db
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

    # finally, make a new contract and don't assign the user to it.
    # we should get a 404, since we're filtering on an org we're not in.

    second_b2b_run, _ = create_contract_run(second_contract, b2b_course)
    second_b2b_run.enrollment_start = one_month_prior
    second_b2b_run.save()

    resp = auth_api_client.get(f"{url}?org_id={second_contract.organization.id}")

    assert resp.status_code == 404


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
