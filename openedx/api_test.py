"""Courseware API tests"""
# pylint: disable=redefined-outer-name
import itertools
from datetime import timedelta
from urllib.parse import parse_qsl

import factory
import pytest
import responses
from django.contrib.auth import get_user_model
from freezegun import freeze_time
from mitol.common.utils.datetime import now_in_utc
from oauth2_provider.models import AccessToken, Application
from oauthlib.common import generate_token
from requests.exceptions import HTTPError
from rest_framework import status

from courses.factories import CourseRunEnrollmentFactory, CourseRunFactory
from main.test_utils import MockHttpError, MockResponse
from openedx.api import (
    ACCESS_TOKEN_HEADER_NAME,
    OPENEDX_AUTH_DEFAULT_TTL_IN_SECONDS,
    OPENEDX_REGISTRATION_VALIDATION_PATH,
    check_username_exists_in_edx,
    create_edx_auth_token,
    create_edx_user,
    create_user,
    enroll_in_edx_course_runs,
    get_edx_api_client,
    get_valid_edx_api_auth,
    repair_faulty_edx_user,
    repair_faulty_openedx_users,
    retry_failed_edx_enrollments,
    subscribe_to_edx_course_emails,
    sync_enrollments_with_edx,
    unsubscribe_from_edx_course_emails,
    update_edx_user_email,
    update_edx_user_name,
)
from openedx.constants import (
    EDX_DEFAULT_ENROLLMENT_MODE,
    EDX_ENROLLMENT_AUDIT_MODE,
    OPENEDX_REPAIR_GRACE_PERIOD_MINS,
    PLATFORM_EDX,
)
from openedx.exceptions import (
    EdxApiEmailSettingsErrorException,
    EdxApiEnrollErrorException,
    EdxApiRegistrationValidationException,
    OpenEdxUserCreateError,
    UnknownEdxApiEmailSettingsException,
    UnknownEdxApiEnrollException,
    UserNameUpdateFailedException,
)
from openedx.factories import OpenEdxApiAuthFactory, OpenEdxUserFactory
from openedx.models import OpenEdxApiAuth, OpenEdxUser
from openedx.utils import SyncResult
from users.factories import UserFactory

User = get_user_model()
pytestmark = [pytest.mark.django_db]


@pytest.fixture()
def application(settings):
    """Test data and settings needed for create_edx_user tests"""
    settings.OPENEDX_OAUTH_APP_NAME = "test_app_name"
    settings.OPENEDX_API_BASE_URL = "http://example.com"
    settings.MITX_ONLINE_OAUTH_PROVIDER = "test_provider"
    settings.MITX_ONLINE_REGISTRATION_ACCESS_TOKEN = "access_token"
    return Application.objects.create(
        name=settings.OPENEDX_OAUTH_APP_NAME,
        user=None,
        client_type="confidential",
        authorization_grant_type="authorization-code",
        skip_authorization=True,
    )


def test_create_user(user, mocker):
    """Test that create_user calls the correct APIs"""
    mock_create_edx_user = mocker.patch("openedx.api.create_edx_user")
    mock_create_edx_auth_token = mocker.patch("openedx.api.create_edx_auth_token")
    create_user(user)
    mock_create_edx_user.assert_called_with(user)
    mock_create_edx_auth_token.assert_called_with(user)


"""
    Adds a mocked response from the EdX username validation API.

    Args:
       username_exists (boolean): Determines whether the mocked response will indicate a matched EdX username (True), or not (False).
       settings (pytest.fixture): Application settings.
       user (str): The username being passed to the EdX username validation API.  This is required if username_exists is True.

    """


def edx_username_validation_response_mock(username_exists, settings, username=None):
    if username_exists:
        validation_decisions = {"username": ""}
    else:
        validation_decisions = {
            "username": f"It looks like {username} belongs to an existing account. Try again with a different username."
        }
    responses.add(
        responses.POST,
        settings.OPENEDX_API_BASE_URL + OPENEDX_REGISTRATION_VALIDATION_PATH,
        json={"validation_decisions": validation_decisions},
        status=status.HTTP_200_OK,
    )


@responses.activate
@pytest.mark.parametrize("access_token_count", [0, 1, 3])
def test_create_edx_user(user, settings, application, access_token_count):
    """Test that create_edx_user makes a request to create an edX user"""
    responses.add(
        responses.POST,
        f"{settings.OPENEDX_API_BASE_URL}/user_api/v1/account/registration/",
        json=dict(success=True),
        status=status.HTTP_200_OK,
    )
    responses.add(
        responses.POST,
        settings.OPENEDX_API_BASE_URL + OPENEDX_REGISTRATION_VALIDATION_PATH,
        json={"validation_decisions": {"username": ""}},
        status=status.HTTP_200_OK,
    )

    for _ in range(access_token_count):
        AccessToken.objects.create(
            user=user,
            application=application,
            token=generate_token(),
            expires=now_in_utc() + timedelta(hours=1),
        )

    create_edx_user(user)

    # An AccessToken should be created during execution
    created_access_token = AccessToken.objects.filter(application=application).last()
    assert (
        responses.calls[0].request.headers[ACCESS_TOKEN_HEADER_NAME]
        == settings.MITX_ONLINE_REGISTRATION_ACCESS_TOKEN
    )
    assert dict(parse_qsl(responses.calls[0].request.body)) == {
        "username": user.username,
        "email": user.email,
        "name": user.name,
        "provider": settings.MITX_ONLINE_OAUTH_PROVIDER,
        "access_token": created_access_token.token,
        "country": "US",
        "honor_code": "True",
    }
    assert (
        OpenEdxUser.objects.filter(
            user=user, platform=PLATFORM_EDX, has_been_synced=True
        ).exists()
        is True
    )


@responses.activate
@pytest.mark.usefixtures("application")
def test_create_edx_user_conflict(settings, user):
    """Test that create_edx_user handles a 409 response from the edX API"""
    responses.add(
        responses.POST,
        f"{settings.OPENEDX_API_BASE_URL}/user_api/v1/account/registration/",
        json=dict(username="exists"),
        status=status.HTTP_409_CONFLICT,
    )
    edx_username_validation_response_mock(False, settings)

    with pytest.raises(OpenEdxUserCreateError):
        create_edx_user(user)

    assert OpenEdxUser.objects.count() == 0


@responses.activate
def test_validate_edx_username_conflict(settings, user):
    """Test that check_username_exists_in_edx handles a username validation conflict"""
    edx_username_validation_response_mock(True, settings, user.username)

    assert check_username_exists_in_edx(user.username) == True


@responses.activate
def test_validate_edx_username_conflict(settings, user):
    """Test that check_username_exists_in_edx raises an exception for non-200 response"""
    responses.add(
        responses.POST,
        settings.OPENEDX_API_BASE_URL + OPENEDX_REGISTRATION_VALIDATION_PATH,
        json={
            "validation_decisions": {
                "username": f"It looks like {user.username} belongs to an existing account. Try again with a different username."
            }
        },
        status=status.HTTP_400_BAD_REQUEST,
    )
    with pytest.raises(EdxApiRegistrationValidationException):
        check_username_exists_in_edx(user.username)


@responses.activate
@freeze_time("2019-03-24 11:50:36")
def test_create_edx_auth_token(settings, user):
    """Tests create_edx_auth_token makes the expected incantations to create a OpenEdxApiAuth"""
    refresh_token = "abc123"
    access_token = "def456"
    code = "ghi789"
    responses.add(
        responses.GET,
        f"{settings.OPENEDX_API_BASE_URL}/auth/login/mitxpro-oauth2/?auth_entry=login",
        status=status.HTTP_200_OK,
    )
    responses.add(
        responses.GET,
        f"{settings.OPENEDX_API_BASE_URL}/oauth2/authorize",
        headers={
            "Location": f"{settings.SITE_BASE_URL}/login/_private/complete?code={code}"
        },
        status=status.HTTP_302_FOUND,
    )
    responses.add(
        responses.GET,
        f"{settings.SITE_BASE_URL}/login/_private/complete",
        status=status.HTTP_200_OK,
    )
    responses.add(
        responses.POST,
        f"{settings.OPENEDX_API_BASE_URL}/oauth2/access_token",
        json=dict(
            refresh_token=refresh_token, access_token=access_token, expires_in=3600
        ),
        status=status.HTTP_200_OK,
    )

    create_edx_auth_token(user)

    assert len(responses.calls) == 4
    assert dict(parse_qsl(responses.calls[3].request.body)) == dict(
        code=code,
        grant_type="authorization_code",
        client_id=settings.OPENEDX_API_CLIENT_ID,
        client_secret=settings.OPENEDX_API_CLIENT_SECRET,
        redirect_uri=f"{settings.SITE_BASE_URL}/login/_private/complete",
    )

    assert OpenEdxApiAuth.objects.filter(user=user).exists()

    auth = OpenEdxApiAuth.objects.get(user=user)

    assert auth.refresh_token == refresh_token
    assert auth.access_token == access_token
    # plus expires_in, minutes 10 seconds
    assert auth.access_token_expires_on == now_in_utc() + timedelta(
        minutes=59, seconds=50
    )


@responses.activate
def test_update_edx_user_email(settings, user):
    """Tests update_edx_user_email makes the expected incantations to update the user"""
    responses.add(
        responses.POST,
        f"{settings.OPENEDX_API_BASE_URL}/user_api/v1/account/registration/",
        json=dict(success=True),
        status=status.HTTP_200_OK,
    )
    responses.add(
        responses.POST,
        settings.OPENEDX_API_BASE_URL + OPENEDX_REGISTRATION_VALIDATION_PATH,
        json={"validation_decisions": {"username": ""}},
        status=status.HTTP_200_OK,
    )

    create_edx_user(user)

    openedx_user_qs = OpenEdxUser.objects.filter(user=user)
    assert openedx_user_qs.exists()
    assert openedx_user_qs.first().user.email != "abc@example.com"

    user.email = "abc@example.com"
    user.save()

    code = "ghi789"
    responses.add(
        responses.GET,
        f"{settings.OPENEDX_API_BASE_URL}/auth/login/mitxpro-oauth2/?auth_entry=login",
        status=status.HTTP_200_OK,
    )
    responses.add(
        responses.GET,
        f"{settings.OPENEDX_API_BASE_URL}/oauth2/authorize",
        headers={
            "Location": f"{settings.SITE_BASE_URL}/login/_private/complete?code={code}"
        },
        status=status.HTTP_302_FOUND,
    )
    responses.add(
        responses.GET,
        f"{settings.SITE_BASE_URL}/login/_private/complete",
        status=status.HTTP_200_OK,
    )

    update_edx_user_email(user)

    assert len(responses.calls) == 4
    assert OpenEdxUser.objects.get(user=user).user.email == "abc@example.com"


@responses.activate
@freeze_time("2019-03-24 11:50:36")
def test_get_valid_edx_api_auth_unexpired():
    """Tests get_valid_edx_api_auth returns the current record if it is valid long enough"""
    auth = OpenEdxApiAuthFactory.create()

    updated_auth = get_valid_edx_api_auth(auth.user)

    assert updated_auth is not None
    assert updated_auth.refresh_token == auth.refresh_token
    assert updated_auth.access_token == auth.access_token
    assert updated_auth.access_token_expires_on == auth.access_token_expires_on


@responses.activate
@freeze_time("2019-03-24 11:50:36")
def test_get_valid_edx_api_auth_expired(settings):
    """Tests get_valid_edx_api_auth fetches and updates the auth credentials if expired"""
    auth = OpenEdxApiAuthFactory.create(expired=True)
    refresh_token = "abc123"
    access_token = "def456"

    responses.add(
        responses.POST,
        f"{settings.OPENEDX_API_BASE_URL}/oauth2/access_token",
        json=dict(
            refresh_token=refresh_token, access_token=access_token, expires_in=3600
        ),
        status=status.HTTP_200_OK,
    )

    updated_auth = get_valid_edx_api_auth(auth.user)

    assert updated_auth is not None
    assert len(responses.calls) == 1
    assert dict(parse_qsl(responses.calls[0].request.body)) == dict(
        refresh_token=auth.refresh_token,
        grant_type="refresh_token",
        client_id=settings.OPENEDX_API_CLIENT_ID,
        client_secret=settings.OPENEDX_API_CLIENT_SECRET,
    )

    assert updated_auth.refresh_token == refresh_token
    assert updated_auth.access_token == access_token
    # plus expires_in, minutes 10 seconds
    assert updated_auth.access_token_expires_on == now_in_utc() + timedelta(
        minutes=59, seconds=50
    )


def test_get_edx_api_client(mocker, settings, user):
    """Tests that get_edx_api_client returns an EdxApi client"""
    settings.OPENEDX_API_BASE_URL = "http://example.com"
    auth = OpenEdxApiAuthFactory.build(user=user)
    mock_refresh = mocker.patch("openedx.api.get_valid_edx_api_auth", return_value=auth)
    client = get_edx_api_client(user)
    assert client.credentials["access_token"] == auth.access_token
    assert client.base_url == settings.OPENEDX_API_BASE_URL
    mock_refresh.assert_called_with(
        user, ttl_in_seconds=OPENEDX_AUTH_DEFAULT_TTL_IN_SECONDS
    )


def test_enroll_in_edx_course_runs(mocker, user):
    """Tests that enroll_in_edx_course_runs uses the EdxApi client to enroll in course runs"""
    mock_client = mocker.MagicMock()
    enroll_return_values = ["result1", "result2"]
    mock_client.enrollments.create_student_enrollment = mocker.Mock(
        side_effect=enroll_return_values
    )
    mocker.patch("openedx.api.get_edx_api_client", return_value=mock_client)
    course_runs = CourseRunFactory.build_batch(2)
    enroll_results = enroll_in_edx_course_runs(user, course_runs)
    mock_client.enrollments.create_student_enrollment.assert_any_call(
        course_runs[0].courseware_id,
        mode=EDX_DEFAULT_ENROLLMENT_MODE,
        username=None,
        force_enrollment=False,
    )
    mock_client.enrollments.create_student_enrollment.assert_any_call(
        course_runs[1].courseware_id,
        mode=EDX_DEFAULT_ENROLLMENT_MODE,
        username=None,
        force_enrollment=False,
    )
    assert enroll_results == enroll_return_values


def test_enroll_api_fail(mocker, user):
    """
    Tests that enroll_in_edx_course_runs raises an EdxApiEnrollErrorException if the request fails
    """
    mock_client = mocker.MagicMock()
    enrollment_response = MockResponse({"message": "no dice"}, status_code=401)
    mock_client.enrollments.create_student_enrollment = mocker.Mock(
        side_effect=HTTPError(response=enrollment_response)
    )
    mocker.patch("openedx.api.get_edx_api_client", return_value=mock_client)
    course_run = CourseRunFactory.build()

    with pytest.raises(EdxApiEnrollErrorException):
        enroll_in_edx_course_runs(user, [course_run])


def test_enroll_pro_unknown_fail(mocker, user):
    """
    Tests that enroll_in_edx_course_runs raises an UnknownEdxApiEnrollException if an unexpected exception
    is encountered
    """
    mock_client = mocker.MagicMock()
    mock_client.enrollments.create_student_enrollment = mocker.Mock(
        side_effect=ValueError("Unexpected error")
    )
    mocker.patch("openedx.api.get_edx_api_client", return_value=mock_client)
    course_run = CourseRunFactory.build()

    with pytest.raises(UnknownEdxApiEnrollException):
        enroll_in_edx_course_runs(user, [course_run])


@pytest.mark.parametrize("exception_raised", [Exception("An error happened"), None])
def test_retry_failed_edx_enrollments(mocker, exception_raised):
    """
    Tests that retry_failed_edx_enrollments loops through enrollments that failed in edX
    and attempts to enroll them again
    """
    with freeze_time(now_in_utc() - timedelta(days=1)):
        failed_enrollments = CourseRunEnrollmentFactory.create_batch(
            3, edx_enrolled=False, user__is_active=True
        )
        CourseRunEnrollmentFactory.create(edx_enrolled=False, user__is_active=False)
    patched_enroll_in_edx = mocker.patch(
        "openedx.api.enroll_in_edx_course_runs",
        side_effect=[None, exception_raised or None, None],
    )
    patched_log_exception = mocker.patch("openedx.api.log.exception")
    successful_enrollments = retry_failed_edx_enrollments()

    assert patched_enroll_in_edx.call_count == len(failed_enrollments)
    assert len(successful_enrollments) == (3 if exception_raised is None else 2)
    assert patched_log_exception.called == bool(exception_raised)
    if exception_raised:
        failed_enroll_user, failed_enroll_runs = patched_enroll_in_edx.call_args_list[
            1
        ][0]
        expected_successful_enrollments = [
            e
            for e in failed_enrollments
            if e.user != failed_enroll_user and e.run != failed_enroll_runs[0]
        ]
        assert {e.id for e in successful_enrollments} == {
            e.id for e in expected_successful_enrollments
        }
        for enrollment in successful_enrollments:
            assert enrollment.edx_emails_subscription is True


def test_retry_failed_enroll_grace_period(mocker):
    """
    Tests that retry_failed_edx_enrollments does not attempt to repair any enrollments that were recently created
    """
    now = now_in_utc()
    with freeze_time(now - timedelta(minutes=OPENEDX_REPAIR_GRACE_PERIOD_MINS - 1)):
        CourseRunEnrollmentFactory.create(edx_enrolled=False, user__is_active=True)
    with freeze_time(now - timedelta(minutes=OPENEDX_REPAIR_GRACE_PERIOD_MINS + 1)):
        older_enrollment = CourseRunEnrollmentFactory.create(
            edx_enrolled=False, user__is_active=True
        )
    patched_enroll_in_edx = mocker.patch("openedx.api.enroll_in_edx_course_runs")
    successful_enrollments = retry_failed_edx_enrollments()

    assert successful_enrollments == [older_enrollment]
    patched_enroll_in_edx.assert_called_once_with(
        older_enrollment.user, [older_enrollment.run], mode=EDX_ENROLLMENT_AUDIT_MODE
    )


@pytest.mark.parametrize(
    "no_openedx_user,no_edx_auth", itertools.product([True, False], [True, False])
)
def test_repair_faulty_edx_user(mocker, user, no_openedx_user, no_edx_auth):
    """
    Tests that repair_faulty_edx_user creates OpenEdxUser/OpenEdxApiAuth objects as necessary and
    returns flags that indicate what was created
    """
    patched_create_edx_user = mocker.patch("openedx.api.create_edx_user")
    patched_create_edx_auth_token = mocker.patch("openedx.api.create_edx_auth_token")
    openedx_user = OpenEdxUserFactory.create(user=user)
    patched_find_object = mocker.patch(
        "openedx.api.find_object_with_matching_attr",
        return_value=None if no_openedx_user else openedx_user,
    )
    openedx_api_auth = None if no_edx_auth else OpenEdxApiAuthFactory.build()
    user.openedx_api_auth = openedx_api_auth

    created_user, created_auth_token = repair_faulty_edx_user(user)
    patched_find_object.assert_called()
    assert patched_create_edx_user.called is no_openedx_user
    assert patched_create_edx_auth_token.called is no_edx_auth
    assert created_user is no_openedx_user
    assert created_auth_token is no_edx_auth


@pytest.mark.parametrize("exception_raised", [MockHttpError, Exception, None])
def test_repair_faulty_openedx_users(mocker, exception_raised):
    """
    Tests that repair_faulty_openedx_users loops through all incorrectly configured Users, attempts to repair
    them, and continues iterating through the Users if an exception is raised
    """
    with freeze_time(now_in_utc() - timedelta(days=1)):
        users = UserFactory.create_batch(3)
    user_count = len(users)
    patched_log_exception = mocker.patch("openedx.api.log.exception")
    patched_faulty_user_qset = mocker.patch(
        "users.models.FaultyOpenEdxUserManager.get_queryset",
        return_value=User.objects.all(),
    )
    patched_repair_user = mocker.patch(
        "openedx.api.repair_faulty_edx_user",
        side_effect=[
            (True, True),
            # Function should continue executing if an exception is thrown
            exception_raised or (True, True),
            (True, True),
        ],
    )
    repaired_users = repair_faulty_openedx_users()

    patched_faulty_user_qset.assert_called_once()
    assert patched_repair_user.call_count == user_count
    assert len(repaired_users) == (3 if exception_raised is None else 2)
    assert patched_log_exception.called == bool(exception_raised)
    if exception_raised:
        failed_user = patched_repair_user.call_args_list[1][0]
        expected_repaired_users = [user for user in users if user != failed_user]
        assert {u.id for u in users} == {u.id for u in expected_repaired_users}


def test_retry_users_grace_period(mocker):
    """
    Tests that repair_faulty_openedx_users does not attempt to repair any users that were recently created
    """
    now = now_in_utc()
    with freeze_time(now - timedelta(minutes=OPENEDX_REPAIR_GRACE_PERIOD_MINS - 1)):
        UserFactory.create()
    with freeze_time(now - timedelta(minutes=OPENEDX_REPAIR_GRACE_PERIOD_MINS + 1)):
        user_to_repair = UserFactory.create()
    patched_faulty_user_qset = mocker.patch(
        "users.models.FaultyOpenEdxUserManager.get_queryset",
        return_value=User.objects.all(),
    )
    patched_repair_user = mocker.patch(
        "openedx.api.repair_faulty_edx_user", return_value=(True, True)
    )
    repaired_users = repair_faulty_openedx_users()

    assert repaired_users == [user_to_repair]
    patched_faulty_user_qset.assert_called_once()
    patched_repair_user.assert_called_once_with(user_to_repair)


# def test_unenroll_edx_course_run(mocker):
#     """Tests that unenroll_edx_course_run makes a call to unenroll in edX via the API client"""
#     mock_client = mocker.MagicMock()
#     run_enrollment = CourseRunEnrollmentFactory.create(edx_enrolled=True)
#     courseware_id = run_enrollment.run.courseware_id
#     enroll_return_value = mocker.Mock(json={"course_id": courseware_id})
#     mock_client.enrollments.deactivate_enrollment = mocker.Mock(
#         return_value=enroll_return_value
#     )
#     mocker.patch("openedx.api.get_edx_api_client", return_value=mock_client)
#     deactivated_enrollment = unenroll_edx_course_run(run_enrollment)
#
#     mock_client.enrollments.deactivate_enrollment.assert_called_once_with(courseware_id)
#     assert deactivated_enrollment == enroll_return_value


# @pytest.mark.parametrize(
#     "client_exception_raised,expected_exception",
#     [
#         [MockHttpError, EdxApiEnrollErrorException],
#         [ValueError, UnknownEdxApiEnrollException],
#         [Exception, UnknownEdxApiEnrollException],
#     ],
# )
# def test_unenroll_edx_course_run_failure(
#     mocker, client_exception_raised, expected_exception
# ):
#     """Tests that unenroll_edx_course_run translates exceptions raised by the API client"""
#     run_enrollment = CourseRunEnrollmentFactory.create(edx_enrolled=True)
#     mock_client = mocker.MagicMock()
#     mock_client.enrollments.deactivate_enrollment = mocker.Mock(
#         side_effect=client_exception_raised
#     )
#     mocker.patch("openedx.api.get_edx_api_client", return_value=mock_client)
#     with pytest.raises(expected_exception):
#         unenroll_edx_course_run(run_enrollment)


def test_update_user_edx_name(mocker, user):
    """Test that update_edx_user makes a call to update update_user_name in edX via API client"""
    user.name = "Test Name"
    mock_client = mocker.MagicMock()
    update_name_return_value = mocker.Mock(
        json={"name": user.name, "username": user.username, "email": user.email}
    )
    mock_client.user_info.update_user_name = mocker.Mock(
        return_value=update_name_return_value
    )
    mocker.patch("openedx.api.get_edx_api_client", return_value=mock_client)
    updated_user = update_edx_user_name(user)
    mock_client.user_info.update_user_name.assert_called_once_with(
        user.username, user.name
    )
    assert update_name_return_value == updated_user


@pytest.mark.parametrize(
    "client_exception_raised,expected_exception",
    [
        [MockHttpError, UserNameUpdateFailedException],
        [ValueError, UserNameUpdateFailedException],
        [Exception, UserNameUpdateFailedException],
    ],
)
def test_update_edx_user_name_failure(
    mocker, client_exception_raised, expected_exception, user
):
    """Tests that update_edx_user_name translates exceptions raised by the API client"""
    mock_client = mocker.MagicMock()
    mock_client.user_info.update_user_name = mocker.Mock(
        side_effect=client_exception_raised
    )
    mocker.patch("openedx.api.get_edx_api_client", return_value=mock_client)
    with pytest.raises(expected_exception):
        update_edx_user_name(user)


def test_sync_enrollments_with_edx_active(mocker, user):
    """sync_enrollments_with_edx should update the 'active' property of existing enrollment records"""
    courseware_ids = [
        "course-v1:abc",
        "course-v1:def",
        "course-v1:ghi",
    ]
    CourseRunEnrollmentFactory.create_batch(
        3,
        user=user,
        run__courseware_id=factory.Iterator(courseware_ids),
        active=factory.Iterator([True, False, False]),
    )
    edx_active_flags = (False, True, False)
    mock_client = mocker.MagicMock()
    mocker.patch("openedx.api.get_edx_api_client", return_value=mock_client)
    mock_client.enrollments.get_student_enrollments = mocker.Mock(
        return_value=mocker.Mock(
            enrollments={
                courseware_id: mocker.Mock(is_active=edx_active_flag)
                for courseware_id, edx_active_flag in zip(
                    courseware_ids, edx_active_flags
                )
            }
        )
    )
    results = sync_enrollments_with_edx(user)
    updated_enrollments = (
        user.courserunenrollment_set(manager="all_objects")
        .filter(run__courseware_id__in=courseware_ids)
        .order_by("run__courseware_id")
    )
    assert [
        (enrollment.run.courseware_id, enrollment.active)
        for enrollment in updated_enrollments
    ] == [
        ("course-v1:abc", False),
        ("course-v1:def", True),
        ("course-v1:ghi", False),
    ]
    assert len(results.created) == 0
    assert len(results.reactivated) == 1
    assert len(results.deactivated) == 1


def test_sync_enrollments_with_edx_new(mocker, user):
    """sync_enrollments_with_edx should create new enrollment records if they exist in edX but not locally"""
    run_id_1 = "course-v1:abc"
    run_id_2 = "course-v1:def"
    CourseRunFactory.create_batch(
        2, courseware_id=factory.Iterator([run_id_1, run_id_2])
    )
    mock_client = mocker.MagicMock()
    mocker.patch("openedx.api.get_edx_api_client", return_value=mock_client)
    mock_client.enrollments.get_student_enrollments = mocker.Mock(
        return_value=mocker.Mock(
            enrollments={
                run_id_1: mocker.Mock(is_active=True),
                run_id_2: mocker.Mock(is_active=False),
            }
        )
    )
    results = sync_enrollments_with_edx(user)
    user_enrollments = user.courserunenrollment_set(manager="all_objects").order_by(
        "run__courseware_id"
    )
    assert [
        (enrollment.run.courseware_id, enrollment.active)
        for enrollment in user_enrollments
    ] == [
        (run_id_1, True),
        (run_id_2, False),
    ]
    assert len(results.created) == 2


def test_sync_enrollments_with_edx_missing(mocker, user):
    """sync_enrollments_with_edx log an error if enrollments exist locally but not in edX"""
    CourseRunEnrollmentFactory.create(user=user, active=True)
    mock_client = mocker.MagicMock()
    mocker.patch("openedx.api.get_edx_api_client", return_value=mock_client)
    patched_log_error = mocker.patch("openedx.api.log.error")
    mock_client.enrollments.get_student_enrollments = mocker.Mock(
        return_value=mocker.Mock(enrollments={})
    )
    results = sync_enrollments_with_edx(user)
    patched_log_error.assert_called_once()
    assert results == SyncResult()


def test_subscribe_to_edx_course_emails(mocker, user):
    """tests that subscribe_to_edx_course_emails makes a call to subscribe for course emails in edX via api client"""
    mock_client = mocker.MagicMock()
    run_enrollment = CourseRunEnrollmentFactory()
    courseware_id = run_enrollment.run.courseware_id
    subscribe_return_value = mocker.Mock(json={"course_id": courseware_id})
    mock_client.email_settings.subscribe = mocker.Mock(
        return_value=subscribe_return_value
    )
    mocker.patch("openedx.api.get_edx_api_client", return_value=mock_client)
    subscribe_to_course_emails = subscribe_to_edx_course_emails(
        user, run_enrollment.run
    )

    mock_client.email_settings.subscribe.assert_called_once_with(courseware_id)
    assert subscribe_to_course_emails == subscribe_return_value


@pytest.mark.parametrize(
    "client_exception_raised, expected_exception",
    [
        [MockHttpError, EdxApiEmailSettingsErrorException],
        [ValueError, UnknownEdxApiEmailSettingsException],
        [Exception, UnknownEdxApiEmailSettingsException],
    ],
)
def test_subscribe_to_edx_course_emails_failure(
    mocker, user, client_exception_raised, expected_exception
):
    """tests that subscribe_to_edx_course_emails translates exceptions raised by api client"""
    mock_client = mocker.MagicMock()
    run_enrollment = CourseRunEnrollmentFactory()
    mock_client.email_settings.subscribe = mocker.Mock(
        side_effect=client_exception_raised
    )
    mocker.patch("openedx.api.get_edx_api_client", return_value=mock_client)

    with pytest.raises(expected_exception):
        subscribe_to_edx_course_emails(user, run_enrollment.run)


def test_unsubscribe_from_edx_course_emails(mocker, user):
    """tests that unsubscribe_from_edx_course_emails makes a call to unsubscribe for course emails in edX via api client"""
    mock_client = mocker.MagicMock()
    run_enrollment = CourseRunEnrollmentFactory()
    courseware_id = run_enrollment.run.courseware_id
    unsubscribe_return_value = mocker.Mock(json={"courseware_id": courseware_id})
    mock_client.email_settings.unsubscribe = mocker.Mock(
        return_value=unsubscribe_return_value
    )
    mocker.patch("openedx.api.get_edx_api_client", return_value=mock_client)
    unsubscribe_to_course_emails = unsubscribe_from_edx_course_emails(
        user, run_enrollment.run
    )

    mock_client.email_settings.unsubscribe.assert_called_once_with(courseware_id)
    assert unsubscribe_to_course_emails == unsubscribe_return_value


@pytest.mark.parametrize(
    "client_exception_raised, expected_exception",
    [
        (MockHttpError, EdxApiEmailSettingsErrorException),
        (ValueError, UnknownEdxApiEmailSettingsException),
        (Exception, UnknownEdxApiEmailSettingsException),
    ],
)
def test_unsubscribe_from_edx_course_emails_failure(
    mocker, user, client_exception_raised, expected_exception
):
    """tests that unsubscribe_from_edx_course_emails translates exception raised by api client"""
    mock_client = mocker.MagicMock()
    run_enrollment = CourseRunEnrollmentFactory()
    mock_client.email_settings.unsubscribe = mocker.Mock(
        side_effect=client_exception_raised
    )
    mocker.patch("openedx.api.get_edx_api_client", return_value=mock_client)

    with pytest.raises(expected_exception):
        unsubscribe_from_edx_course_emails(user, run_enrollment.run)
