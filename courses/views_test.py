"""
Tests for course views
"""
# pylint: disable=unused-argument, redefined-outer-name
import operator as op
from datetime import timedelta

import pytest
from django.contrib.auth.models import AnonymousUser
from django.urls import reverse
from mitol.common.utils.datetime import now_in_utc
from rest_framework import status

from courses.api import UserEnrollments
from courses.factories import (
    CourseFactory,
    CourseRunEnrollmentFactory,
    CourseRunFactory,
    ProgramEnrollmentFactory,
    ProgramFactory,
)
from courses.serializers import (
    CourseRunSerializer,
    CourseSerializer,
    ProgramSerializer,
    CourseRunEnrollmentSerializer,
)
from courses.views.v1 import UserEnrollmentsView
from main.test_utils import assert_drf_json_equal

pytestmark = [pytest.mark.django_db]


@pytest.fixture()
def programs():
    """Fixture for a set of Programs in the database"""
    return ProgramFactory.create_batch(3)


@pytest.fixture()
def courses():
    """Fixture for a set of Courses in the database"""
    return CourseFactory.create_batch(3)


@pytest.fixture()
def course_runs():
    """Fixture for a set of CourseRuns in the database"""
    return CourseRunFactory.create_batch(3)


def test_get_programs(user_drf_client, programs):
    """Test the view that handles requests for all Programs"""
    resp = user_drf_client.get(reverse("programs_api-list"))
    programs_data = sorted(resp.json(), key=op.itemgetter("id"))
    assert len(programs_data) == len(programs)
    for program, program_data in zip(programs, programs_data):
        assert_drf_json_equal(program_data, ProgramSerializer(program).data)


def test_get_program(user_drf_client, programs):
    """Test the view that handles a request for single Program"""
    program = programs[0]
    resp = user_drf_client.get(
        reverse("programs_api-detail", kwargs={"pk": program.id})
    )
    program_data = resp.json()
    assert_drf_json_equal(program_data, ProgramSerializer(program).data)


def test_create_program(user_drf_client, programs):
    """Test the view that handles a request to create a Program"""
    program = programs[0]
    program_data = ProgramSerializer(program).data
    del program_data["id"]
    program_data["title"] = "New Program Title"
    request_url = reverse("programs_api-list")
    resp = user_drf_client.post(request_url, program_data)
    assert resp.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


def test_patch_program(user_drf_client, programs):
    """Test the view that handles a request to patch a Program"""
    program = programs[0]
    request_url = reverse("programs_api-detail", kwargs={"pk": program.id})
    resp = user_drf_client.patch(request_url, {"title": "New Program Title"})
    assert resp.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


def test_delete_program(user_drf_client, programs):
    """Test the view that handles a request to delete a Program"""
    program = programs[0]
    resp = user_drf_client.delete(
        reverse("programs_api-detail", kwargs={"pk": program.id})
    )
    assert resp.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


@pytest.mark.parametrize("is_anonymous", [True, False])
def test_get_courses(user_drf_client, courses, mock_context, is_anonymous):
    """Test the view that handles requests for all Courses"""
    if is_anonymous:
        user_drf_client.logout()
    resp = user_drf_client.get(reverse("courses_api-list"))
    courses_data = resp.json()
    assert len(courses_data) == len(courses)
    for course, course_data in zip(courses, courses_data):
        assert (
            course_data == CourseSerializer(instance=course, context=mock_context).data
        )


@pytest.mark.parametrize("is_anonymous", [True, False])
def test_get_course(user_drf_client, courses, mock_context, is_anonymous):
    """Test the view that handles a request for single Course"""
    if is_anonymous:
        user_drf_client.logout()
    course = courses[0]
    resp = user_drf_client.get(reverse("courses_api-detail", kwargs={"pk": course.id}))
    course_data = resp.json()
    assert course_data == CourseSerializer(instance=course, context=mock_context).data


def test_create_course(user_drf_client, courses, mock_context):
    """Test the view that handles a request to create a Course"""
    course = courses[0]
    course_data = CourseSerializer(instance=course, context=mock_context).data
    del course_data["id"]
    course_data["title"] = "New Course Title"
    request_url = reverse("courses_api-list")
    resp = user_drf_client.post(request_url, course_data)
    assert resp.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


def test_patch_course(user_drf_client, courses):
    """Test the view that handles a request to patch a Course"""
    course = courses[0]
    request_url = reverse("courses_api-detail", kwargs={"pk": course.id})
    resp = user_drf_client.patch(request_url, {"title": "New Course Title"})
    assert resp.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


def test_delete_course(user_drf_client, courses):
    """Test the view that handles a request to delete a Course"""
    course = courses[0]
    resp = user_drf_client.delete(
        reverse("courses_api-detail", kwargs={"pk": course.id})
    )
    assert resp.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


def test_get_course_runs(user_drf_client, course_runs):
    """Test the view that handles requests for all CourseRuns"""
    resp = user_drf_client.get(reverse("course_runs_api-list"))
    course_runs_data = resp.json()
    assert len(course_runs_data) == len(course_runs)
    # Force sorting by run id since this test has been flaky
    course_runs_data = sorted(course_runs_data, key=op.itemgetter("id"))
    for course_run, course_run_data in zip(course_runs, course_runs_data):
        assert course_run_data == CourseRunSerializer(course_run).data


def test_get_course_run(user_drf_client, course_runs):
    """Test the view that handles a request for single CourseRun"""
    course_run = course_runs[0]
    resp = user_drf_client.get(
        reverse("course_runs_api-detail", kwargs={"pk": course_run.id})
    )
    course_run_data = resp.json()
    assert course_run_data == CourseRunSerializer(course_run).data


def test_create_course_run(user_drf_client, course_runs):
    """Test the view that handles a request to create a CourseRun"""
    course_run = course_runs[0]
    course_run_data = CourseRunSerializer(course_run).data
    del course_run_data["id"]
    course_run_data.update(
        {
            "title": "New CourseRun Title",
            "courseware_id": "new-courserun-id",
            "courseware_url_path": "http://example.com",
        }
    )
    request_url = reverse("course_runs_api-list")
    resp = user_drf_client.post(request_url, course_run_data)
    assert resp.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


def test_patch_course_run(user_drf_client, course_runs):
    """Test the view that handles a request to patch a CourseRun"""
    course_run = course_runs[0]
    request_url = reverse("course_runs_api-detail", kwargs={"pk": course_run.id})
    resp = user_drf_client.patch(request_url, {"title": "New CourseRun Title"})
    assert resp.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


def test_delete_course_run(user_drf_client, course_runs):
    """Test the view does not handle a request to delete a CourseRun"""
    course_run = course_runs[0]
    resp = user_drf_client.delete(
        reverse("course_runs_api-detail", kwargs={"pk": course_run.id})
    )
    assert resp.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


@pytest.mark.parametrize("live", [True, False])
def test_programs_not_live(client, live):
    """Programs should be filtered out if live=False"""
    program = ProgramFactory.create(live=live)
    resp = client.get(reverse("programs_api-list"))
    assert resp.status_code == status.HTTP_200_OK
    assert_drf_json_equal(
        resp.json(), [ProgramSerializer(program).data] if live else []
    )


@pytest.mark.parametrize("live", [True, False])
def test_courses_not_live_in_programs_api(client, live):
    """Courses should be filtered out of the programs API if not live"""
    course = CourseFactory.create(live=live, program__live=True)
    resp = client.get(reverse("programs_api-list"))
    assert resp.status_code == status.HTTP_200_OK
    assert_drf_json_equal(
        resp.json()[0]["courses"], [CourseSerializer(course).data] if live else []
    )


@pytest.mark.parametrize("live", [True, False])
def test_courses_not_live_in_courses_api(client, live):
    """Courses should be filtered out of the courses API if not live"""
    course = CourseFactory.create(live=live)
    resp = client.get(reverse("courses_api-list"))
    assert resp.status_code == status.HTTP_200_OK
    assert_drf_json_equal(resp.json(), [CourseSerializer(course).data] if live else [])


@pytest.mark.parametrize("live", [True, False])
def test_course_runs_not_live_in_courses_api(client, live):
    """Course runs should be filtered out of the courses API if not live"""
    run = CourseRunFactory.create(live=live, course__live=True)
    resp = client.get(reverse("courses_api-list"))
    assert resp.status_code == status.HTTP_200_OK
    assert_drf_json_equal(
        resp.json()[0]["courseruns"], [CourseRunSerializer(run).data] if live else []
    )


def test_user_enrollments_list(user_drf_client, user):
    """The user enrollments view should return serialized enrollments for the logged-in user"""
    assert UserEnrollmentsView.serializer_class == CourseRunEnrollmentSerializer
    user_run_enrollment = CourseRunEnrollmentFactory.create(user=user)
    CourseRunEnrollmentFactory.create()
    resp = user_drf_client.get(reverse("user-enrollments"))
    assert resp.status_code == status.HTTP_200_OK
    assert_drf_json_equal(
        resp.json(),
        [
            CourseRunEnrollmentSerializer(
                user_run_enrollment, context={"include_page_fields": True}
            ).data
        ],
    )
