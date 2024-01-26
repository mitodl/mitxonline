"""
Tests for courses api views v2
"""
import operator as op
import random

import pytest
from django.urls import reverse
from rest_framework import status
from django.db import connection
import logging

from courses.conftest import course_catalog_data
from courses.factories import DepartmentFactory
from courses.serializers.v2.programs import ProgramSerializer
from courses.serializers.v2.courses import CourseWithCourseRunsSerializer
from courses.serializers.v2.departments import DepartmentWithCountSerializer
from courses.views.test_utils import (
    num_queries_from_programs,
    num_queries_from_course,
    num_queries_from_department,
)
from courses.views.v2 import Pagination
from fixtures.common import raise_nplusone
from main.test_utils import assert_drf_json_equal, duplicate_queries_check

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
        empty_departments_from_fixture.append(
            DepartmentWithCountSerializer(
                instance=department, context=mock_context
            ).data
        )
    with django_assert_max_num_queries(
        num_queries_from_department(len(departments))
    ) as context:
        resp = user_drf_client.get(reverse("v2:departments_api-list"))
    duplicate_queries_check(context)
    empty_departments_data = resp.json()["results"]
    assert_drf_json_equal(
        empty_departments_data, empty_departments_from_fixture, ignore_order=True
    )

    courses, programs, _ = course_catalog_data
    for course in courses:
        course.departments.add(random.choice(departments))
    for program in programs:
        program.departments.add(random.choice(departments))
    with django_assert_max_num_queries(
        num_queries_from_department(len(departments))
    ) as context:
        resp = user_drf_client.get(reverse("v2:departments_api-list"))
    duplicate_queries_check(context)
    departments_data = resp.json()["results"]
    departments_from_fixture = []
    for department in departments:
        departments_from_fixture.append(
            DepartmentWithCountSerializer(
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
    _, programs, _ = course_catalog_data
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
@pytest.mark.parametrize("course_catalog_program_count", [15], indirect=True)
@pytest.mark.parametrize("include_finaid", [True, False])
def test_get_courses(
    user_drf_client,
    mock_context,
    django_assert_max_num_queries,
    course_catalog_data,
    include_finaid,
):
    """Test the view that handles requests for all Courses"""
    courses, _, _ = course_catalog_data
    courses_from_fixture = []
    num_queries = 0

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
            f"test_get_course logged {query_count_end - query_count_start} queries"
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
            f"test_get_course logged {query_count_end - query_count_start} queries"
        )
    duplicate_queries_check(context)
    course_data = resp.json()
    course_from_fixture = dict(
        CourseWithCourseRunsSerializer(instance=course, context=mock_context).data
    )
    assert_drf_json_equal(course_data, course_from_fixture, ignore_order=True)
