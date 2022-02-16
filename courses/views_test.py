"""
Tests for course views
"""
# pylint: disable=unused-argument, redefined-outer-name, too-many-arguments
import operator as op

import pytest
from django.db.models import Count, Q
from django.urls import reverse
from requests import HTTPError, ConnectionError as RequestsConnectionError
from rest_framework import status

from courses.constants import ENROLL_CHANGE_STATUS_UNENROLLED
from courses.factories import (
    CourseFactory,
    CourseRunEnrollmentFactory,
    CourseRunFactory,
    ProgramFactory,
    BlockedCountryFactory,
)
from courses.models import CourseRun
from courses.serializers import (
    CourseRunSerializer,
    CourseSerializer,
    ProgramSerializer,
    CourseRunEnrollmentSerializer,
)
from courses.views.v1 import UserEnrollmentsApiViewSet
from main import features
from main.constants import (
    USER_MSG_COOKIE_NAME,
    USER_MSG_TYPE_ENROLL_BLOCKED,
    USER_MSG_TYPE_ENROLLED,
    USER_MSG_TYPE_ENROLL_FAILED,
)
from main.test_utils import assert_drf_json_equal
from openedx.exceptions import NoEdxApiAuthError
from main.utils import encode_json_cookie_value

pytestmark = [pytest.mark.django_db]


EXAMPLE_URL = "http://example.com"


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


@pytest.mark.parametrize("is_enrolled", [True, False])
def test_get_course_runs_relevant(
    mocker, user_drf_client, course_runs, user, is_enrolled
):
    """A GET request for course runs with a `relevant_to` parameter should return user-relevant course runs"""
    course_run = course_runs[0]
    user_enrollments = Count(
        "enrollments",
        filter=Q(
            enrollments__user=user,
            enrollments__active=True,
            enrollments__edx_enrolled=True,
        ),
    )
    patched_run_qset = mocker.patch(
        "courses.views.v1.get_user_relevant_course_run_qset",
        return_value=CourseRun.objects.filter(id=course_run.id)
        .annotate(user_enrollments=user_enrollments)
        .order_by("-user_enrollments", "enrollment_start"),
    )

    if is_enrolled:
        CourseRunEnrollmentFactory.create(user=user, run=course_run, edx_enrolled=True)

    resp = user_drf_client.get(
        f"{reverse('course_runs_api-list')}?relevant_to={course_run.course.readable_id}"
    )
    patched_run_qset.assert_called_once_with(course_run.course, user)
    course_run_data = resp.json()[0]

    assert course_run_data["is_enrolled"] == is_enrolled


def test_get_course_runs_relevant_missing(user_drf_client):
    """A GET request for course runs with an invalid `relevant_to` query parameter should return empty results"""
    resp = user_drf_client.get(
        f"{reverse('course_runs_api-list')}?relevant_to=invalid+course+id"
    )
    course_runs_data = resp.json()
    assert course_runs_data == []


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
    assert UserEnrollmentsApiViewSet.serializer_class == CourseRunEnrollmentSerializer
    user_run_enrollment = CourseRunEnrollmentFactory.create(user=user)
    CourseRunEnrollmentFactory.create()
    resp = user_drf_client.get(reverse("user-enrollments-api-list"))
    assert resp.status_code == status.HTTP_200_OK
    assert_drf_json_equal(
        resp.json(),
        [
            CourseRunEnrollmentSerializer(
                user_run_enrollment, context={"include_page_fields": True}
            ).data
        ],
    )


@pytest.mark.parametrize("sync_dashboard_flag", [True, False])
def test_user_enrollments_list_sync(
    mocker, settings, user_drf_client, user, sync_dashboard_flag
):
    """
    If the appropriate feature flag is turned on, the enrollments list API call should sync enrollments with
    """
    settings.FEATURES[features.SYNC_ON_DASHBOARD_LOAD] = sync_dashboard_flag
    patched_sync = mocker.patch(
        "courses.views.v1.sync_enrollments_with_edx",
    )
    resp = user_drf_client.get(reverse("user-enrollments-api-list"))
    assert resp.status_code == status.HTTP_200_OK
    assert patched_sync.called is sync_dashboard_flag
    if sync_dashboard_flag is True:
        patched_sync.assert_called_once_with(user)


@pytest.mark.parametrize("exception_raised", [NoEdxApiAuthError, HTTPError, ValueError])
def test_user_enrollments_list_sync_fail(
    mocker, settings, user_drf_client, user, exception_raised
):
    """
    The enrollments list API should log an exception and continue if enrollment syncing fails for any reason
    """
    settings.FEATURES[features.SYNC_ON_DASHBOARD_LOAD] = True
    patched_sync = mocker.patch(
        "courses.views.v1.sync_enrollments_with_edx", side_effect=exception_raised
    )
    patched_log_exception = mocker.patch("courses.views.v1.log.exception")
    resp = user_drf_client.get(reverse("user-enrollments-api-list"))
    assert resp.status_code == status.HTTP_200_OK
    patched_sync.assert_called_once()
    patched_log_exception.assert_called_once()


@pytest.mark.parametrize("ignore_failures_flag", [True, False])
def test_user_enrollments_create(
    mocker, settings, user_drf_client, user, ignore_failures_flag
):
    """The user enrollments view should succeed when creating a new enrollment"""
    settings.FEATURES[features.IGNORE_EDX_FAILURES] = ignore_failures_flag
    run = CourseRunFactory.create()
    fake_enrollment = {"fake": "enrollment"}
    patched_enroll = mocker.patch(
        "courses.serializers.create_run_enrollments",
        return_value=([fake_enrollment], True),
    )
    resp = user_drf_client.post(
        reverse("user-enrollments-api-list"), data={"run_id": run.id}
    )
    assert resp.status_code == status.HTTP_201_CREATED
    patched_enroll.assert_called_once_with(
        user,
        [run],
        keep_failed_enrollments=ignore_failures_flag,
    )
    # Running a request to create the enrollment again should succeed
    resp = user_drf_client.post(
        reverse("user-enrollments-api-list"), data={"run_id": run.id}
    )
    assert resp.status_code == status.HTTP_201_CREATED


def test_user_enrollments_create_invalid(user_drf_client, user):
    """The user enrollments view should fail when creating a new enrollment with an invalid run id"""
    resp = user_drf_client.post(
        reverse("user-enrollments-api-list"), data={"run_id": 1234}
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert resp.json() == {"errors": {"run_id": f"Invalid course run id: 1234"}}


@pytest.mark.parametrize(
    "deactivate_fail, exp_success, exp_status_code",
    [
        [False, True, status.HTTP_204_NO_CONTENT],
        [True, False, status.HTTP_400_BAD_REQUEST],
    ],
)
def test_user_enrollment_delete(
    mocker,
    settings,
    user_drf_client,
    user,
    deactivate_fail,
    exp_success,
    exp_status_code,
):
    """
    The user enrollment view DELETE handler should unenroll in edX and deactivate the local enrollment record, and
    return the appropriate status code depending on the success of the unenrollment.
    """
    settings.FEATURES[features.IGNORE_EDX_FAILURES] = False
    enrollment = CourseRunEnrollmentFactory.create(
        user=user, active=True, change_status=None
    )
    inactive_enrollment = CourseRunEnrollmentFactory.create(
        user=user,
        active=False,
        change_status=ENROLL_CHANGE_STATUS_UNENROLLED,
        edx_emails_subscription=False,
    )
    patched_deactivate = mocker.patch(
        "courses.views.v1.deactivate_run_enrollment",
        return_value=(None if deactivate_fail else inactive_enrollment),
    )
    resp = user_drf_client.delete(
        reverse("user-enrollments-api-detail", kwargs={"pk": enrollment.id})
    )
    patched_deactivate.assert_called_once_with(
        enrollment,
        change_status=ENROLL_CHANGE_STATUS_UNENROLLED,
        keep_failed_enrollments=False,
    )
    assert resp.status_code == exp_status_code
    final_enrollment = patched_deactivate.return_value
    assert final_enrollment == None if deactivate_fail else inactive_enrollment
    if not deactivate_fail:
        assert final_enrollment.edx_emails_subscription is False


def test_user_enrollment_delete_other_fail(mocker, settings, user_drf_client, user):
    """
    The user enrollment view DELETE handler should reject a request to deactivate another user's enrollment
    """
    other_user_enrollment = CourseRunEnrollmentFactory.create(
        user__username="other-user", active=True, change_status=None
    )
    patched_deactivate = mocker.patch("courses.views.v1.deactivate_run_enrollment")
    resp = user_drf_client.delete(
        reverse("user-enrollments-api-detail", kwargs={"pk": other_user_enrollment.id})
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    patched_deactivate.assert_not_called()


def test_create_enrollments(mocker, user_client):
    """Create enrollment view should create an enrollment and include a user message in the response cookies"""
    patched_create_enrollments = mocker.patch(
        "courses.views.v1.create_run_enrollments",
        return_value=(None, True),
    )
    run = CourseRunFactory.create()
    resp = user_client.post(
        reverse("create-enrollment-via-form"),
        data={"run": str(run.id)},
    )
    assert resp.status_code == status.HTTP_302_FOUND
    assert resp.url == reverse("user-dashboard")
    assert USER_MSG_COOKIE_NAME in resp.cookies
    assert resp.cookies[USER_MSG_COOKIE_NAME].value == encode_json_cookie_value(
        {
            "type": USER_MSG_TYPE_ENROLLED,
            "run": run.title,
        }
    )
    patched_create_enrollments.assert_called_once()


def test_create_enrollments_failed(mocker, settings, user_client):
    """
    Create enrollment view should redirect and include a user message in the response cookies if the enrollment
    request to edX fails
    """
    settings.FEATURES[features.IGNORE_EDX_FAILURES] = False
    patched_create_enrollments = mocker.patch(
        "courses.views.v1.create_run_enrollments",
        return_value=(None, False),
    )
    run = CourseRunFactory.create()
    resp = user_client.post(
        reverse("create-enrollment-via-form"),
        data={"run": str(run.id)},
        HTTP_REFERER=EXAMPLE_URL,
    )
    assert resp.status_code == status.HTTP_302_FOUND
    assert resp.url == EXAMPLE_URL
    assert USER_MSG_COOKIE_NAME in resp.cookies
    assert resp.cookies[USER_MSG_COOKIE_NAME].value == encode_json_cookie_value(
        {
            "type": USER_MSG_TYPE_ENROLL_FAILED,
        }
    )
    patched_create_enrollments.assert_called_once()


def test_create_enrollments_no_run(mocker, user_client):
    """Create enrollment view should redirect if the run doesn't exist"""
    patched_log_error = mocker.patch("courses.views.v1.log.error")
    resp = user_client.post(
        reverse("create-enrollment-via-form"),
        data={"run": "1234"},
        HTTP_REFERER=EXAMPLE_URL,
    )
    assert resp.status_code == status.HTTP_302_FOUND
    patched_log_error.assert_called_once()
    assert resp.url == EXAMPLE_URL


def test_create_enrollments_blocked_country(user_client, user):
    """
    Create enrollment view should redirect with a user message in a cookie if the attempted enrollment is blocked
    """
    run = CourseRunFactory.create()
    BlockedCountryFactory.create(course=run.course, country=user.legal_address.country)
    resp = user_client.post(
        reverse("create-enrollment-via-form"),
        data={"run": str(run.id)},
        HTTP_REFERER=EXAMPLE_URL,
    )
    assert resp.status_code == status.HTTP_302_FOUND
    assert resp.url == EXAMPLE_URL
    assert USER_MSG_COOKIE_NAME in resp.cookies
    assert resp.cookies[USER_MSG_COOKIE_NAME].value == encode_json_cookie_value(
        {
            "type": USER_MSG_TYPE_ENROLL_BLOCKED,
        }
    )


@pytest.mark.parametrize("receive_emails", [True, False])
def test_update_user_enrollment(mocker, user_drf_client, user, receive_emails):
    """the enrollment should update the course email subscriptions"""
    run_enrollment = CourseRunEnrollmentFactory.create(user=user)
    fake_enrollment = {"fake": "enrollment"}
    patch_func = (
        "subscribe_to_edx_course_emails"
        if receive_emails
        else "unsubscribe_from_edx_course_emails"
    )
    patched_email_subscription = mocker.patch(
        f"courses.views.v1.{patch_func}", return_value=fake_enrollment
    )
    resp = user_drf_client.patch(
        reverse("user-enrollments-api-detail", kwargs={"pk": run_enrollment.id}),
        data={"receive_emails": "on" if receive_emails else ""},
    )
    assert resp.status_code == status.HTTP_200_OK
    patched_email_subscription.assert_called_once_with(user, run_enrollment.run)


@pytest.mark.parametrize("receive_emails", [True, False])
@pytest.mark.parametrize(
    "exception_raised", [NoEdxApiAuthError, HTTPError, RequestsConnectionError]
)
def test_update_user_enrollment_failure(
    mocker, user_drf_client, user, receive_emails, exception_raised
):
    """the enrollment update failure to the course email subscriptions"""
    run_enrollment = CourseRunEnrollmentFactory.create(user=user)
    patch_func = (
        "subscribe_to_edx_course_emails"
        if receive_emails
        else "unsubscribe_from_edx_course_emails"
    )
    patched_email_subscription = mocker.patch(
        f"courses.views.v1.{patch_func}", side_effect=exception_raised
    )
    patched_log_exception = mocker.patch("courses.views.v1.log.exception")
    resp = user_drf_client.patch(
        reverse("user-enrollments-api-detail", kwargs={"pk": run_enrollment.id}),
        data={"receive_emails": "on" if receive_emails else ""},
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    patched_email_subscription.assert_called_once_with(user, run_enrollment.run)
    patched_log_exception.assert_called_once()
