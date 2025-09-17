"""Courseware API tests"""

# pylint: disable=redefined-outer-name
import itertools
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import parse_qsl

import factory
import pytest
import responses
from django.contrib.auth import get_user_model
from freezegun import freeze_time
from mitol.common.utils.datetime import now_in_utc
from mitol.common.utils.user import _reformat_for_username, usernameify
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
    bulk_retire_edx_users,
    create_edx_auth_token,
    create_edx_user,
    create_user,
    enroll_in_edx_course_runs,
    existing_edx_enrollment,
    get_edx_api_client,
    get_edx_retirement_service_client,
    get_valid_edx_api_auth,
    reconcile_edx_username,
    repair_all_faulty_openedx_users,
    repair_faulty_edx_user,
    repair_faulty_openedx_users,
    retry_failed_edx_enrollments,
    subscribe_to_edx_course_emails,
    sync_enrollments_with_edx,
    unenroll_edx_course_run,
    unsubscribe_from_edx_course_emails,
    update_edx_user_email,
    update_edx_user_name,
    update_edx_user_profile,
    validate_username_email_with_edx,
    _generate_unique_username,
)
from openedx.constants import (
    EDX_DEFAULT_ENROLLMENT_MODE,
    EDX_ENROLLMENT_AUDIT_MODE,
    EDX_ENROLLMENT_VERIFIED_MODE,
    OPENEDX_REPAIR_GRACE_PERIOD_MINS,
    OPENEDX_USERNAME_MAX_LEN,
    PLATFORM_EDX,
)
from openedx.exceptions import (
    EdxApiEmailSettingsErrorException,
    EdxApiEnrollErrorException,
    EdxApiRegistrationValidationException,
    EdxApiUserUpdateError,
    OpenEdxUserMissingError,
    UnknownEdxApiEmailSettingsException,
    UnknownEdxApiEnrollException,
    UserNameUpdateFailedException,
)
from openedx.factories import OpenEdxApiAuthFactory
from openedx.models import OpenEdxApiAuth, OpenEdxUser
from openedx.utils import SyncResult
from users.factories import UserFactory

User = get_user_model()
pytestmark = [pytest.mark.django_db]


@pytest.fixture
def application(settings):
    """Test data and settings needed for create_edx_user tests"""
    settings.OPENEDX_OAUTH_APP_NAME = "test_app_name"
    settings.OPENEDX_API_BASE_URL = "http://example.com"
    settings.OPENEDX_OAUTH_PROVIDER = "test_provider"
    settings.MITX_ONLINE_REGISTRATION_ACCESS_TOKEN = "access_token"  # noqa: S105
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
    mock_create_edx_user.assert_called_with(user, None)
    mock_create_edx_auth_token.assert_called_with(user)


def edx_username_validation_response_mock(username_exists, settings):
    """
    Adds a mocked response from the EdX username validation API.

    Args:
       username_exists (boolean): Determines whether the mocked response will indicate a matched EdX username (True), or not (False).
       settings (pytest.fixture): Application settings.
       user (str): The username being passed to the EdX username validation API.  This is required if username_exists is True.

    """
    if username_exists:
        validation_decisions = {"username": ""}
    else:
        validation_decisions = {
            "username": "It looks like this username is already taken"
        }
    responses.add(
        responses.POST,
        settings.OPENEDX_API_BASE_URL + OPENEDX_REGISTRATION_VALIDATION_PATH,
        json={"validation_decisions": validation_decisions},
        status=status.HTTP_200_OK,
    )


@responses.activate
@pytest.mark.parametrize(
    "has_been_synced",
    [pytest.param(True, id="synced:true"), pytest.param(False, id="synced:false")],
)
@pytest.mark.parametrize("access_token_count", [0, 1, 3])
@pytest.mark.parametrize(
    "provided_username",
    ["test_username", None],
)
@pytest.mark.parametrize(
    "missing_username",
    [
        pytest.param(True, id="missing_username:true"),
        pytest.param(False, id="missing_username:false"),
    ],
)
def test_create_edx_user(  # noqa: PLR0913
    settings,
    application,
    has_been_synced,
    access_token_count,
    provided_username,
    missing_username,
):
    """Test that create_edx_user makes a request to create an edX user"""
    if has_been_synced and missing_username:
        pytest.skip("Invalidation combination")

    user = UserFactory.create(openedx_user__has_been_synced=has_been_synced)
    openedx_user = user.openedx_users.first()
    if missing_username:
        openedx_user.edx_username = None
        openedx_user.save()

    original_username = user.edx_username
    resp1 = responses.add(
        responses.GET,
        f"{settings.OPENEDX_API_BASE_URL}/api/mobile/v0.5/my_user_info",
        json={},
        status=status.HTTP_200_OK,
    )
    resp2 = responses.add(
        responses.POST,
        f"{settings.OPENEDX_API_BASE_URL}/user_api/v1/account/registration/",
        json=dict(success=True),  # noqa: C408
        status=status.HTTP_200_OK,
    )

    for _ in range(access_token_count):
        AccessToken.objects.create(
            user=user,
            application=application,
            token=generate_token(),
            expires=now_in_utc() + timedelta(hours=1),
        )

    if provided_username:
        create_edx_user(user, provided_username)
    else:
        create_edx_user(user)

    # An AccessToken should be created during execution
    created_access_token = AccessToken.objects.filter(application=application).last()

    assert resp1.call_count == (1 if has_been_synced else 0)

    if not has_been_synced:
        assert resp2.call_count == 1

        assert (
            resp2.calls[0].request.headers[ACCESS_TOKEN_HEADER_NAME]
            == settings.MITX_ONLINE_REGISTRATION_ACCESS_TOKEN
        )
        expected_request_body = {
            "email": user.email,
            "name": user.name,
            "provider": settings.OPENEDX_OAUTH_PROVIDER,
            "access_token": created_access_token.token,
            "country": user.legal_address.country if user.legal_address else None,
            "year_of_birth": (
                str(user.user_profile.year_of_birth) if user.user_profile else None
            ),
            "gender": user.user_profile.gender if user.user_profile else None,
            "honor_code": "True",
        }
        if not missing_username:
            expected_request_body["username"] = original_username
        elif provided_username:
            expected_request_body["username"] = provided_username
        else:
            expected_request_body["username"] = usernameify(
                user.name, user.email, OPENEDX_USERNAME_MAX_LEN
            )
        assert dict(parse_qsl(resp2.calls[0].request.body)) == expected_request_body
    else:
        assert resp2.call_count == 0

    assert OpenEdxUser.objects.filter(
        user=user, platform=PLATFORM_EDX, has_been_synced=True
    ).exists()

    if provided_username and missing_username:
        assert user.openedx_users.first().edx_username == provided_username
    elif provided_username and not missing_username:
        assert user.openedx_users.first().edx_username == original_username


@responses.activate
@pytest.mark.usefixtures("application")
@pytest.mark.parametrize(
    ("username_suggestions", "base_username", "expected_username_pattern", "test_description"),
    [
        (
            ["openedx-generated-username"],
            "testuser",
            lambda username: username == "openedx-generated-username",
            "with OpenEdX suggestions"
        ),
        (
            [],
            "José",
            lambda username: username.startswith("José_") and len(username) > len("José"),
            "with empty suggestions (non-ASCII fallback)"
        ),
    ],
)
def test_create_edx_user_conflict(settings, username_suggestions, base_username, expected_username_pattern, test_description):
    """Test that create_edx_user handles a 409 response from the edX API"""
    user = UserFactory.create(
        openedx_user__has_been_synced=False,
        openedx_user__desired_edx_username=base_username
    )

    resp1 = responses.add(
        responses.GET,
        f"{settings.OPENEDX_API_BASE_URL}/api/mobile/v0.5/my_user_info",
        json={},
        status=status.HTTP_200_OK,
    )
    resp2 = responses.add(
        responses.POST,
        f"{settings.OPENEDX_API_BASE_URL}/user_api/v1/account/registration/",
        json={
            "error_code": "duplicate-username",
            "username_suggestions": username_suggestions,
        },
        status=status.HTTP_409_CONFLICT,
    )

    resp3 = responses.add(
        responses.POST,
        f"{settings.OPENEDX_API_BASE_URL}/user_api/v1/account/registration/",
        json=dict(success=True),  # noqa: C408
        status=status.HTTP_200_OK,
    )
    edx_username_validation_response_mock(False, settings)  # noqa: FBT003

    create_edx_user(user)

    assert resp1.call_count == 0
    assert resp2.call_count == 1
    assert resp3.call_count == 1

    user.refresh_from_db()

    edx_user = user.openedx_users.first()

    assert edx_user.has_been_synced is True
    assert expected_username_pattern(edx_user.edx_username), f"Username {edx_user.edx_username} doesn't match expected pattern for {test_description}"


@pytest.mark.parametrize(
    ("base_username", "expected_prefix"),
    [
        ("testuser", "testuser_"),
        ("José", "José_"),
        ("user123", "user123_"),
    ],
)
def test_generate_unique_username(base_username, expected_prefix):
    """Test that _generate_unique_username generates unique usernames"""
    
    username = _generate_unique_username(base_username)
    assert username.startswith(expected_prefix)
    assert len(username) > len(base_username)


@responses.activate
@pytest.mark.parametrize(
    "open_edx_user_record_exists,open_edx_user_record_has_been_synced",  # noqa: PT006
    itertools.product([True, False], [True, False]),
)
def test_create_edx_user_for_user_not_synced_with_edx(
    mocker,
    settings,
    user,
    open_edx_user_record_exists,
    open_edx_user_record_has_been_synced,
):
    """Test that create_edx_user validates the user record on Edx if an OpenEdxUser record already exists."""

    responses.add(
        responses.POST,
        f"{settings.OPENEDX_API_BASE_URL}/user_api/v1/account/registration/",
        json=dict(success=True),  # noqa: C408
        status=status.HTTP_200_OK,
    )
    user.openedx_users.update(has_been_synced=open_edx_user_record_has_been_synced)

    mock_client = mocker.MagicMock()
    mock_client.user_info.get_user_info = mocker.Mock(
        side_effect=Exception if not open_edx_user_record_exists else None,
    )
    mocker.patch("openedx.api.get_edx_api_client", return_value=mock_client)

    user_created_in_edx = create_edx_user(user)

    assert OpenEdxUser.objects.get(user=user).has_been_synced is True
    assert user_created_in_edx is not (
        open_edx_user_record_exists and open_edx_user_record_has_been_synced
    )


@responses.activate
def test_validate_edx_username_conflict(settings, user):
    """Test that validate_username_email_with_edx handles a username validation conflict"""
    edx_username_validation_response_mock(True, settings)  # noqa: FBT003

    assert validate_username_email_with_edx(user.edx_username, "example@mit.edu")


@responses.activate
def test_validate_edx_username_conflict(settings, user):  # noqa: F811
    """Test that validate_username_email_with_edx raises an exception for non-200 response"""
    responses.add(
        responses.POST,
        settings.OPENEDX_API_BASE_URL + OPENEDX_REGISTRATION_VALIDATION_PATH,
        json={
            "validation_decisions": {
                "username": "It looks like this username is already taken"
            }
        },
        status=status.HTTP_400_BAD_REQUEST,
    )
    with pytest.raises(EdxApiRegistrationValidationException):
        validate_username_email_with_edx(user.edx_username, "example@mit.edu")


@responses.activate
@freeze_time("2019-03-24 11:50:36")
def test_create_edx_auth_token(settings):
    """Tests create_edx_auth_token makes the expected incantations to create a OpenEdxApiAuth"""
    refresh_token = "abc123"  # noqa: S105
    access_token = "def456"  # noqa: S105
    code = "ghi789"

    user = UserFactory.create(no_openedx_api_auth=True)

    responses.add(
        responses.GET,
        f"{settings.OPENEDX_API_BASE_URL}{settings.OPENEDX_SOCIAL_LOGIN_PATH}",
        status=status.HTTP_200_OK,
    )
    responses.add(
        responses.GET,
        f"{settings.OPENEDX_API_BASE_URL}/oauth2/authorize",
        headers={"Location": f"{settings.SITE_BASE_URL}/_/auth/complete?code={code}"},
        status=status.HTTP_302_FOUND,
    )
    responses.add(
        responses.GET,
        f"{settings.SITE_BASE_URL}/_/auth/complete",
        status=status.HTTP_200_OK,
    )
    responses.add(
        responses.POST,
        f"{settings.OPENEDX_API_BASE_URL}/oauth2/access_token",
        json=dict(  # noqa: C408
            refresh_token=refresh_token, access_token=access_token, expires_in=3600
        ),
        status=status.HTTP_200_OK,
    )

    create_edx_auth_token(user)

    assert len(responses.calls) == 4
    assert dict(parse_qsl(responses.calls[3].request.body)) == dict(  # noqa: C408
        code=code,
        grant_type="authorization_code",
        client_id=settings.OPENEDX_API_CLIENT_ID,
        client_secret=settings.OPENEDX_API_CLIENT_SECRET,
        redirect_uri=f"{settings.SITE_BASE_URL}/_/auth/complete",
    )

    assert OpenEdxApiAuth.objects.filter(user=user).exists()

    auth = OpenEdxApiAuth.objects.get(user=user)

    assert auth.refresh_token == refresh_token
    assert auth.access_token == access_token
    assert auth.access_token_expires_on == now_in_utc() + timedelta(
        minutes=59, seconds=50
    )


@responses.activate
def test_update_edx_user_email(settings):
    """Tests update_edx_user_email makes the expected incantations to update the user"""
    user = UserFactory.create(openedx_user__has_been_synced=False)

    responses.add(
        responses.POST,
        f"{settings.OPENEDX_API_BASE_URL}/user_api/v1/account/registration/",
        json=dict(success=True),  # noqa: C408
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
        f"{settings.OPENEDX_API_BASE_URL}{settings.OPENEDX_SOCIAL_LOGIN_PATH}",
        status=status.HTTP_200_OK,
    )
    responses.add(
        responses.GET,
        f"{settings.OPENEDX_API_BASE_URL}/oauth2/authorize",
        headers={"Location": f"{settings.SITE_BASE_URL}/_/auth/complete?code={code}"},
        status=status.HTTP_302_FOUND,
    )
    responses.add(
        responses.GET,
        f"{settings.SITE_BASE_URL}/_/auth/complete",
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
    refresh_token = "abc123"  # noqa: S105
    access_token = "def456"  # noqa: S105

    responses.add(
        responses.POST,
        f"{settings.OPENEDX_API_BASE_URL}/oauth2/access_token",
        json=dict(  # noqa: C408
            refresh_token=refresh_token, access_token=access_token, expires_in=3600
        ),
        status=status.HTTP_200_OK,
    )

    updated_auth = get_valid_edx_api_auth(auth.user)

    assert updated_auth is not None
    assert len(responses.calls) == 1
    assert dict(parse_qsl(responses.calls[0].request.body)) == dict(  # noqa: C408
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


def test_get_edx_retirement_service_client(mocker, settings):
    """Tests that get_edx_retirement_service_client returns an EdxApi client"""

    settings.OPENEDX_API_BASE_URL = "http://example.com"
    settings.OPENEDX_RETIREMENT_SERVICE_WORKER_CLIENT_ID = (
        "OPENEDX_RETIREMENT_SERVICE_WORKER_CLIENT_ID"
    )
    settings.OPENEDX_RETIREMENT_SERVICE_WORKER_CLIENT_SECRET = (
        "OPENEDX_RETIREMENT_SERVICE_WORKER_CLIENT_SECRET"  # noqa: S105
    )
    mock_resp = mocker.Mock()
    mock_resp.json.return_value = {"access_token": "an_access_token"}
    mock_resp.json.status_code = 200
    mock_resp.raise_for_status.side_effect = None
    mocker.patch("openedx.api.requests.post", return_value=mock_resp)
    client = get_edx_retirement_service_client()
    assert client.credentials["access_token"] == "an_access_token"  # noqa: S105
    assert client.base_url == settings.OPENEDX_API_BASE_URL


@pytest.mark.parametrize("has_edx_username", [True, False])
def test_enroll_in_edx_course_runs(settings, mocker, user, has_edx_username):
    """Tests that enroll_in_edx_course_runs uses the EdxApi client to enroll in course runs"""
    settings.OPENEDX_SERVICE_WORKER_API_TOKEN = "mock_api_token"  # noqa: S105
    mock_client = mocker.MagicMock()
    enroll_return_values = [
        mocker.Mock(is_active=True),
        mocker.Mock(is_active=False),
        mocker.Mock(is_active=True),
    ]
    mock_client.enrollments.create_student_enrollment = mocker.Mock(
        side_effect=enroll_return_values
    )
    mocker.patch("openedx.api.get_edx_api_client", return_value=mock_client)
    mocker.patch("openedx.api.get_edx_api_service_client", return_value=mock_client)
    course_runs = CourseRunFactory.build_batch(2)

    # Test to make sure reconcile_edx_username runs as expected.
    if not has_edx_username:
        user.openedx_users.all().delete()
        user.refresh_from_db()

        with pytest.raises(OpenEdxUserMissingError) as e:
            enroll_results = enroll_in_edx_course_runs(user, course_runs)

        assert e.type is OpenEdxUserMissingError
        assert user.openedx_users.count() == 0
        return

    enroll_results = enroll_in_edx_course_runs(user, course_runs)

    mock_client.enrollments.create_student_enrollment.assert_any_call(
        course_runs[0].courseware_id,
        mode=EDX_DEFAULT_ENROLLMENT_MODE,
        username=user.edx_username,
        force_enrollment=True,
    )
    mock_client.enrollments.create_student_enrollment.assert_any_call(
        course_runs[1].courseware_id,
        mode=EDX_DEFAULT_ENROLLMENT_MODE,
        username=user.edx_username,
        force_enrollment=True,
    )
    assert enroll_results == [enroll_return_values[0], enroll_return_values[2]]


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
    mocker.patch("openedx.api.get_edx_api_service_client", return_value=mock_client)
    course_run = CourseRunFactory.build()

    with pytest.raises(EdxApiEnrollErrorException):
        enroll_in_edx_course_runs(user, [course_run])


def test_enroll_pro_unknown_fail(settings, mocker, user):
    """
    Tests that enroll_in_edx_course_runs raises an UnknownEdxApiEnrollException if an unexpected exception
    is encountered
    """
    settings.OPENEDX_SERVICE_WORKER_API_TOKEN = "mock_api_token"  # noqa: S105
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
    "no_openedx_user,no_edx_auth",  # noqa: PT006
    itertools.product([True, False], [True, False]),
)
def test_repair_faulty_edx_user(mocker, no_openedx_user, no_edx_auth):
    """
    Tests that repair_faulty_edx_user creates OpenEdxUser/OpenEdxApiAuth objects as necessary and
    returns flags that indicate what was created
    """
    user = UserFactory.create(
        no_openedx_user=no_openedx_user, no_openedx_api_auth=no_edx_auth
    )

    patched_create_edx_auth_token = mocker.patch("openedx.api.create_edx_auth_token")
    mocker.patch(
        "openedx.api.create_edx_user",
        return_value=True if no_openedx_user else False,  # noqa: SIM210
    )

    created_user, created_auth_token = repair_faulty_edx_user(user)

    if no_edx_auth:
        patched_create_edx_auth_token.assert_called_once_with(user)
    else:
        patched_create_edx_auth_token.assert_not_called()
    assert created_user is no_openedx_user
    assert created_auth_token is no_edx_auth


def _create_faulty_users():
    """Create a set of users that meet the criteria of being in a faulty state"""
    # these users shouldn't be picked up
    UserFactory.create()
    UserFactory.create(
        no_openedx_api_auth=True,
        openedx_user__has_been_synced=False,
        openedx_user__has_sync_error=True,
    )

    # same as the ones that get returned, but no last_login excludes them
    UserFactory.create(last_login=None, no_openedx_user=True)
    UserFactory.create(last_login=None, no_openedx_api_auth=True)
    UserFactory.create(last_login=None, openedx_user__has_been_synced=False)

    return [
        UserFactory.create(no_openedx_user=True),
        UserFactory.create(no_openedx_api_auth=True),
        UserFactory.create(openedx_user__has_been_synced=False),
    ]


def test_repair_all_faulty_openedx_users(mocker):
    """
    Tests that repair_faulty_openedx_users loops through all incorrectly configured Users, attempts to repair
    them, and continues iterating through the Users if an exception is raised
    """
    with freeze_time(now_in_utc() - timedelta(days=1)):
        users = _create_faulty_users()

    patched_repair_users = mocker.patch(
        "openedx.api.repair_faulty_openedx_users",
    )

    repair_all_faulty_openedx_users()

    assert patched_repair_users.call_count == 1
    assert list(patched_repair_users.call_args.args[0]) == users


@pytest.mark.parametrize("exception_raised", [MockHttpError, Exception, None])
def test_repair_faulty_openedx_users(mocker, exception_raised):
    """
    Tests that repair_faulty_openedx_users loops through all incorrectly configured Users, attempts to repair
    them, and continues iterating through the Users if an exception is raised
    """
    with freeze_time(now_in_utc() - timedelta(days=1)):
        users = _create_faulty_users()

    patched_log_exception = mocker.patch("openedx.api.log.exception")
    patched_repair_user = mocker.patch(
        "openedx.api.repair_faulty_edx_user",
        side_effect=[
            (True, True),
            # Function should continue executing if an exception is thrown
            exception_raised or (True, True),
            (True, True),
        ],
    )
    repair_faulty_openedx_users(users)

    assert patched_repair_user.call_count == len(users), (
        patched_repair_user.call_args_list
    )

    assert patched_log_exception.called == bool(exception_raised)

    for user in users:
        patched_repair_user.assert_any_call(user)


def test_retry_users_grace_period(mocker):
    """
    Tests that repair_all_faulty_openedx_users does not attempt to repair any users that were recently created
    """
    now = now_in_utc()
    with freeze_time(now - timedelta(minutes=OPENEDX_REPAIR_GRACE_PERIOD_MINS - 1)):
        _create_faulty_users()
    with freeze_time(now - timedelta(minutes=OPENEDX_REPAIR_GRACE_PERIOD_MINS + 1)):
        users_to_repair = _create_faulty_users()
    patched_repair_users = mocker.patch("openedx.api.repair_faulty_openedx_users")

    repair_all_faulty_openedx_users()

    assert patched_repair_users.call_count == 1

    assert list(patched_repair_users.call_args.args[0]) == users_to_repair


def test_unenroll_edx_course_run(mocker):
    """Tests that unenroll_edx_course_run makes a call to unenroll in edX via the API client"""
    mock_client = mocker.MagicMock()
    run_enrollment = CourseRunEnrollmentFactory.create(edx_enrolled=True)
    courseware_id = run_enrollment.run.courseware_id
    username = run_enrollment.user.edx_username
    enroll_return_value = mocker.Mock(
        json={"course_id": courseware_id, "user": username}
    )
    mock_client.enrollments.deactivate_enrollment = mocker.Mock(
        return_value=enroll_return_value
    )
    mocker.patch("openedx.api.get_edx_api_service_client", return_value=mock_client)
    deactivated_enrollment = unenroll_edx_course_run(run_enrollment)

    mock_client.enrollments.deactivate_enrollment.assert_called_once_with(
        courseware_id, username=username
    )
    assert deactivated_enrollment == enroll_return_value


def test_update_user_edx_name(mocker, user):
    """Test that update_edx_user makes a call to update update_user_name in edX via API client"""
    user.name = "Test Name"
    mock_client = mocker.MagicMock()
    update_name_return_value = mocker.Mock(
        json={"name": user.name, "username": user.edx_username, "email": user.email}
    )
    mock_client.user_info.update_user_name = mocker.Mock(
        return_value=update_name_return_value
    )
    mocker.patch("openedx.api.get_edx_api_client", return_value=mock_client)
    updated_user = update_edx_user_name(user)
    mock_client.user_info.update_user_name.assert_called_once_with(
        user.edx_username, user.name
    )
    assert update_name_return_value == updated_user


@pytest.mark.parametrize(
    "client_exception_raised,expected_exception",  # noqa: PT006
    [
        [MockHttpError, UserNameUpdateFailedException],  # noqa: PT007
        [ValueError, UserNameUpdateFailedException],  # noqa: PT007
        [Exception, UserNameUpdateFailedException],  # noqa: PT007
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
    """Tests that subscribe_to_edx_course_emails makes a call to subscribe for course emails in edX via api client"""
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
    "client_exception_raised, expected_exception",  # noqa: PT006
    [
        [MockHttpError, EdxApiEmailSettingsErrorException],  # noqa: PT007
        [ValueError, UnknownEdxApiEmailSettingsException],  # noqa: PT007
        [Exception, UnknownEdxApiEmailSettingsException],  # noqa: PT007
    ],
)
def test_subscribe_to_edx_course_emails_failure(
    mocker, user, client_exception_raised, expected_exception
):
    """Tests that subscribe_to_edx_course_emails translates exceptions raised by api client"""
    mock_client = mocker.MagicMock()
    run_enrollment = CourseRunEnrollmentFactory()
    mock_client.email_settings.subscribe = mocker.Mock(
        side_effect=client_exception_raised
    )
    mocker.patch("openedx.api.get_edx_api_client", return_value=mock_client)

    with pytest.raises(expected_exception):
        subscribe_to_edx_course_emails(user, run_enrollment.run)


def test_unsubscribe_from_edx_course_emails(mocker, user):
    """Tests that unsubscribe_from_edx_course_emails makes a call to unsubscribe for course emails in edX via api client"""
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
    "client_exception_raised, expected_exception",  # noqa: PT006
    [
        (MockHttpError, EdxApiEmailSettingsErrorException),
        (ValueError, UnknownEdxApiEmailSettingsException),
        (Exception, UnknownEdxApiEmailSettingsException),
    ],
)
def test_unsubscribe_from_edx_course_emails_failure(
    mocker, user, client_exception_raised, expected_exception
):
    """Tests that unsubscribe_from_edx_course_emails translates exception raised by api client"""
    mock_client = mocker.MagicMock()
    run_enrollment = CourseRunEnrollmentFactory()
    mock_client.email_settings.unsubscribe = mocker.Mock(
        side_effect=client_exception_raised
    )
    mocker.patch("openedx.api.get_edx_api_client", return_value=mock_client)

    with pytest.raises(expected_exception):
        unsubscribe_from_edx_course_emails(user, run_enrollment.run)


@pytest.mark.parametrize(
    "edx_enrollment_is_active, edx_enrollment_mode, enrollment_mode_to_match, enrollment_is_active_to_match, existing_edx_enrollment_found",  # noqa: PT006
    [
        (True, EDX_ENROLLMENT_AUDIT_MODE, EDX_ENROLLMENT_AUDIT_MODE, True, True),
        (False, EDX_ENROLLMENT_AUDIT_MODE, EDX_ENROLLMENT_AUDIT_MODE, True, False),
        (True, EDX_ENROLLMENT_AUDIT_MODE, EDX_ENROLLMENT_VERIFIED_MODE, True, False),
        (True, EDX_ENROLLMENT_VERIFIED_MODE, EDX_ENROLLMENT_VERIFIED_MODE, True, True),
        (
            False,
            EDX_ENROLLMENT_VERIFIED_MODE,
            EDX_ENROLLMENT_VERIFIED_MODE,
            True,
            False,
        ),
        (True, EDX_ENROLLMENT_VERIFIED_MODE, EDX_ENROLLMENT_AUDIT_MODE, True, False),
        (True, EDX_ENROLLMENT_AUDIT_MODE, EDX_ENROLLMENT_AUDIT_MODE, False, False),
        (True, EDX_ENROLLMENT_AUDIT_MODE, EDX_ENROLLMENT_VERIFIED_MODE, False, False),
    ],
)
def test_existing_edx_enrollment(  # noqa: PLR0913
    mocker,
    user,
    edx_enrollment_is_active,
    edx_enrollment_mode,
    enrollment_mode_to_match,
    enrollment_is_active_to_match,
    existing_edx_enrollment_found,
):
    """existing_edx_enrollment should return enrollments matching parameters provided."""
    run_id = "course-v1:abc"
    mock_client = mocker.MagicMock()
    mocker.patch("openedx.api.get_edx_api_service_client", return_value=mock_client)

    mock_client.enrollments.get_enrollments = mocker.Mock(
        return_value=[
            mocker.Mock(mode=edx_enrollment_mode, is_active=edx_enrollment_is_active)
        ]
    )

    if existing_edx_enrollment_found:
        assert (
            existing_edx_enrollment(
                user,
                run_id,
                enrollment_mode_to_match,
                is_active=enrollment_is_active_to_match,
            )
            is not None
        )
    else:
        assert (
            existing_edx_enrollment(
                user,
                run_id,
                enrollment_mode_to_match,
                is_active=enrollment_is_active_to_match,
            )
            is None
        )


def test_bulk_retire_edx_users(mocker):
    """Tests that bulk_retire_edx_users calls the edX bulk retirement api via the edx api client"""
    test_usernames = "test_username1,test_username2"
    mock_client = mocker.MagicMock()
    mock_get_edx_retirement_service_client = mocker.patch(
        "openedx.api.get_edx_retirement_service_client", return_value=mock_client
    )
    mock_client.bulk_user_retirement.retire_users = mocker.Mock(
        return_value={
            "successful_user_retirements": ["test_username1", "test_username2"]
        }
    )
    resp = bulk_retire_edx_users(test_usernames)
    assert resp["successful_user_retirements"] == ["test_username1", "test_username2"]
    mock_get_edx_retirement_service_client.assert_called()
    mock_client.bulk_user_retirement.retire_users.assert_called_with(
        {"usernames": test_usernames}
    )


@pytest.mark.parametrize("name_is_empty", [True, False])
def test_reconcile_edx_username(name_is_empty):
    """Ensure the edX username reconciliation works properly."""

    user = UserFactory.create(openedx_user=None)
    if name_is_empty:
        user.name = ""
        user.save()

    assert reconcile_edx_username(user)

    user.refresh_from_db()

    assert user.openedx_users.count() == 1

    if name_is_empty:
        assert user.openedx_users.get().edx_username == _reformat_for_username(
            user.email.split("@")[0]
        )
    else:
        assert user.openedx_users.get().edx_username == _reformat_for_username(
            user.name
        )


def test_reconcile_edx_username_conflict():
    """Test that reconciling the username adds suffixes properly if there's a conflict"""

    user = UserFactory.create(
        username="bobjones@place.email",
        name="Bob Jones",
        legal_address__first_name="Bob",
        legal_address__last_name="Jones",
        openedx_user=None,
    )
    assert reconcile_edx_username(user)

    user.refresh_from_db()

    new_user = UserFactory.create(
        username="bobjones@other.place.email",
        openedx_user=None,
        name="Bob Jones",
        legal_address__first_name=user.legal_address.first_name,
        legal_address__last_name=user.legal_address.last_name,
    )
    assert reconcile_edx_username(new_user)

    new_user.refresh_from_db()

    assert user.edx_username in new_user.edx_username
    assert user.edx_username != new_user.edx_username


@patch("openedx.api.get_valid_edx_api_auth")
@patch("openedx.api.requests.Session")
def test_update_edx_user_profile_success(mock_session, mock_get_auth, mocker, user):
    """
    Test that update_edx_user_profile makes a call to update the user profile in Open edX via an API client
    """
    mock_auth = mocker.MagicMock()
    mock_auth.access_token = "token"  # noqa: S105
    mock_get_auth.return_value = mock_auth

    mock_resp = mocker.MagicMock()
    mock_resp.status_code = 200
    mock_session.return_value.patch.return_value = mock_resp

    update_edx_user_profile(user)
    mock_session.return_value.patch.assert_called_once()


@patch("openedx.api.get_valid_edx_api_auth")
@patch("openedx.api.requests.Session")
def test_update_edx_user_profile_no_openedx_user(
    mock_session, mock_get_auth, user, caplog
):
    """
    Test that update_edx_user_profile does not attempt to update the user profile in Open edX when Open edX user is not synced
    """
    user.openedx_users.all().delete()
    update_edx_user_profile(user)
    assert "Skipping user profile update" in caplog.text


@patch("openedx.api.get_valid_edx_api_auth")
@patch("openedx.api.requests.Session")
def test_update_edx_user_profile_error(mock_session, mock_get_auth, mocker, user):
    """
    Test that update_edx_user_profile raises an EdxApiUserUpdateError if the request fails
    """
    mock_auth = mocker.MagicMock()
    mock_auth.access_token = "token"  # noqa: S105
    mock_get_auth.return_value = mock_auth

    mock_resp = mocker.MagicMock()
    mock_resp.status_code = 400
    mock_session.return_value.patch.return_value = mock_resp

    with patch("openedx.api.get_error_response_summary", return_value="error summary"):
        with pytest.raises(EdxApiUserUpdateError) as exc:
            update_edx_user_profile(user)
        assert "Error updating Open edX user" in str(exc.value)
