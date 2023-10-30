"""
Tests for courses api views v2
"""
import operator as op

import pytest
from django.urls import reverse
from rest_framework import status

from courses.conftest import course_catalog_data
from courses.serializers.v2 import ProgramSerializer
from courses.views.test_utils import (
    num_queries_from_programs,
)
from fixtures.common import raise_nplusone
from main.test_utils import assert_drf_json_equal, duplicate_queries_check

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("raise_nplusone")]


@pytest.mark.parametrize("course_catalog_course_count", [100], indirect=True)
@pytest.mark.parametrize("course_catalog_program_count", [15], indirect=True)
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
    assert len(programs_data) == len(programs)
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
    program_data = ProgramSerializer(program, "v2").data
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
