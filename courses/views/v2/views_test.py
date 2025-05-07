"""
Tests for courses api views v2
"""

import logging
import random

import pytest
from django.db import connection
from django.urls import reverse
from b2b.api import create_contract_run
from b2b.factories import ContractPageFactory, OrganizationPageFactory
from rest_framework import status
from django.contrib.auth.models import AnonymousUser
from django.test.client import RequestFactory
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory
from courses.factories import CourseFactory, CourseRunFactory, DepartmentFactory
from courses.models import Course, Program
from courses.serializers.v2.courses import CourseWithCourseRunsSerializer
from courses.serializers.v2.departments import (
    DepartmentWithCoursesAndProgramsSerializer,
)
from courses.serializers.v2.programs import ProgramSerializer
from courses.views.test_utils import (
    num_queries_from_course,
    num_queries_from_department,
    num_queries_from_programs,
)
from courses.views.v2 import CourseFilterSet, Pagination
from main.test_utils import assert_drf_json_equal, duplicate_queries_check
from users.factories import UserFactory

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("raise_nplusone")]


logger = logging.getLogger(__name__)


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


@pytest.mark.parametrize("course_catalog_course_count", [100], indirect=True)
@pytest.mark.parametrize("course_catalog_program_count", [12], indirect=True)
def test_get_programs(
    user_drf_client, django_assert_max_num_queries, course_catalog_data
):
    """Test the view that handles requests for all Programs"""
    course_catalog_data  # noqa: B018

    # Fetch programs after running the fixture so they're in the right order
    programs = Program.objects.order_by("title").prefetch_related("departments").all()

    num_queries = num_queries_from_programs(programs, "v2")
    with django_assert_max_num_queries(num_queries) as context:
        resp = user_drf_client.get(reverse("v2:programs_api-list"))
    duplicate_queries_check(context)
    programs_data = resp.json()["results"]
    assert len(programs_data) == Pagination.page_size
    for program, program_data in zip(programs, programs_data):
        assert_drf_json_equal(
            program_data, ProgramSerializer(program).data, ignore_order=True
        )


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


@pytest.mark.parametrize("course_catalog_course_count", [100], indirect=True)
@pytest.mark.parametrize("course_catalog_program_count", [12], indirect=True)
@pytest.mark.parametrize("include_finaid", [True, False])
def test_get_courses(
    user_drf_client,
    mock_context,
    django_assert_max_num_queries,
    course_catalog_data,
    include_finaid,
):
    """Test the view that handles requests for all Courses"""
    course_catalog_data  # noqa: B018
    courses_from_fixture = []
    num_queries = 0

    courses = Course.objects.order_by("title").prefetch_related("departments").all()

    if include_finaid:
        mock_context["include_approved_financial_aid"] = True

    for course in courses:
        courses_from_fixture.append(
            CourseWithCourseRunsSerializer(instance=course, context=mock_context).data
        )
        num_queries += num_queries_from_course(course, "v1")
    with django_assert_max_num_queries(num_queries) as context:
        query_count_start = len(connection.queries)
        resp = user_drf_client.get(
            reverse("v2:courses_api-list"),
            {
                "include_approved_financial_aid": include_finaid,
                "page_size": len(courses_from_fixture),
            },
        )
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
def test_filter_with_org_id_returns_contracted_course(user_drf_client):
    org = OrganizationPageFactory(name="Test Org")
    contract = ContractPageFactory(organization=org, active=True)
    course = CourseFactory(title="Contracted Course")
    create_contract_run(contract, course)

    unrelated_course = Course.objects.create(title="Other Course")
    CourseRunFactory(course=unrelated_course)

    url = reverse("v2:courses_api-list")
    response = user_drf_client.get(url, {"org_id": org.id})

    titles = [result["title"] for result in response.data["results"]]
    assert course.title in titles
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

def test_filter_anonymous_user_sees_no_contracted_runs():
    course_with_contract = CourseFactory(title="Hidden Course")
    contract = ContractPageFactory(active=True)
    CourseRunFactory(course=course_with_contract, b2b_contract=contract)

    course_no_contract = CourseFactory(title="Visible Course")
    CourseRunFactory(course=course_no_contract)
    rf = RequestFactory()
    request = rf.get(reverse("v2:courses_api-list"))
    request.user = AnonymousUser()
    drf_request = Request(request)
    queryset = Course.objects.all()
    filtered = CourseFilterSet(data=drf_request.query_params, request=drf_request, queryset=queryset).qs

    assert course_no_contract in filtered
    assert course_with_contract not in filtered
