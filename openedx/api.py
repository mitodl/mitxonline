"""Courseware API functions"""

import logging
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.shortcuts import reverse
from edx_api.client import EdxApi
from edx_api.course_runs.exceptions import CourseRunAPIError
from edx_api.course_runs.models import CourseRun, CourseRunList
from mitol.common.utils import (
    find_object_with_matching_attr,
    get_error_response_summary,
    now_in_utc,
    usernameify,
)
from oauth2_provider.models import AccessToken, Application
from oauthlib.common import generate_token
from requests.exceptions import HTTPError
from rest_framework import status

import courses.models
from authentication import api as auth_api
from courses.constants import ENROLL_CHANGE_STATUS_UNENROLLED
from main.utils import get_partitioned_set_difference
from openedx.constants import (
    EDX_DEFAULT_ENROLLMENT_MODE,
    OPENEDX_REPAIR_GRACE_PERIOD_MINS,
    OPENEDX_USERNAME_MAX_LEN,
    PLATFORM_EDX,
)
from openedx.exceptions import (
    EdxApiEmailSettingsErrorException,
    EdxApiEnrollErrorException,
    EdxApiRegistrationValidationException,
    EdxApiUserDoesNotExistError,
    EdxApiUserUpdateError,
    NoEdxApiAuthError,
    OpenEdXOAuth2Error,
    OpenEdxUserCreateError,
    UnknownEdxApiEmailSettingsException,
    UnknownEdxApiEnrollException,
    UserNameUpdateFailedException,
)
from openedx.models import OpenEdxApiAuth, OpenEdxUser
from openedx.utils import SyncResult, edx_url

log = logging.getLogger(__name__)
User = get_user_model()

OPENEDX_REGISTER_USER_PATH = "/user_api/v1/account/registration/"
OPENEDX_REGISTRATION_VALIDATION_PATH = "/api/user/v1/validation/registration"
OPENEDX_UPDATE_USER_PATH = "/api/user/v1/accounts/"
OPENEDX_REQUEST_DEFAULTS = dict(honor_code=True)  # noqa: C408

OPENEDX_SOCIAL_LOGIN_PATH = settings.OPENEDX_SOCIAL_LOGIN_PATH
OPENEDX_OAUTH2_AUTHORIZE_PATH = "/oauth2/authorize"
OPENEDX_OAUTH2_ACCESS_TOKEN_PATH = "/oauth2/access_token"  # noqa: S105
OPENEDX_OAUTH2_SCOPES = ["read", "write"]
OPENEDX_OAUTH2_ACCESS_TOKEN_PARAM = "code"  # noqa: S105
OPENEDX_OAUTH2_ACCESS_TOKEN_EXPIRY_MARGIN_SECONDS = 10

OPENEDX_AUTH_DEFAULT_TTL_IN_SECONDS = 60
OPENEDX_AUTH_MAX_TTL_IN_SECONDS = 60 * 60

OPENEDX_AUTH_COMPLETE_URL = "openedx-private-oauth-complete-no-apisix"

ACCESS_TOKEN_HEADER_NAME = "X-Access-Token"  # noqa: S105


def create_user(user, edx_username=None):
    """
    Creates a user and any related artifacts in the openedx

    Args:
        user (user.models.User): the application user
    """

    create_edx_user(user, edx_username)
    create_edx_auth_token(user)


def create_edx_user(user, edx_username=None):
    """
    Makes a request to create an equivalent user in Open edX

    Args:
        user (user.models.User): the application user
        edx_username (str): the username to use in Open edX
    """
    application = Application.objects.get(name=settings.OPENEDX_OAUTH_APP_NAME)
    expiry_date = now_in_utc() + timedelta(hours=settings.OPENEDX_TOKEN_EXPIRES_HOURS)
    access_token = AccessToken.objects.create(
        user=user, application=application, token=generate_token(), expires=expiry_date
    )

    open_edx_user, _ = OpenEdxUser.objects.get_or_create(
        user=user,
        platform=PLATFORM_EDX,
        defaults={"edx_username": edx_username or None},
    )

    if open_edx_user.edx_username is None and edx_username is not None:
        open_edx_user.edx_username = edx_username
        open_edx_user.save()

    with transaction.atomic():
        open_edx_user = OpenEdxUser.objects.select_for_update().get(
            user=user,
            platform=PLATFORM_EDX,
        )

        if not open_edx_user.edx_username:
            # no username has been set so skip this
            return False

        if open_edx_user.has_been_synced:
            # Here we should check with edx that the user exists on that end.
            try:
                client = get_edx_api_client(user)
                client.user_info.get_user_info()
            except:  # noqa: S110, E722
                pass
            else:
                open_edx_user.has_been_synced = True
                open_edx_user.save()
                return False

        # a non-200 status here will ensure we rollback creation of the OpenEdxUser and try again
        req_session = requests.Session()
        if settings.MITX_ONLINE_REGISTRATION_ACCESS_TOKEN is not None:
            req_session.headers.update(
                {
                    ACCESS_TOKEN_HEADER_NAME: settings.MITX_ONLINE_REGISTRATION_ACCESS_TOKEN
                }
            )
        resp = req_session.post(
            edx_url(OPENEDX_REGISTER_USER_PATH),
            data=dict(
                username=open_edx_user.edx_username,
                email=user.email,
                name=user.name,
                country=user.legal_address.country if user.legal_address else None,
                state=user.legal_address.us_state if user.legal_address else None,
                gender=user.user_profile.gender if user.user_profile else None,
                year_of_birth=(
                    user.user_profile.year_of_birth if user.user_profile else None
                ),
                level_of_education=(
                    user.user_profile.level_of_education if user.user_profile else None
                ),
                provider=settings.OPENEDX_OAUTH_PROVIDER,
                access_token=access_token.token,
                **OPENEDX_REQUEST_DEFAULTS,
            ),
        )
        # edX responds with 200 on success, not 201
        if resp.status_code != status.HTTP_200_OK:
            raise OpenEdxUserCreateError(
                f"Error creating Open edX user. {get_error_response_summary(resp)}"  # noqa: EM102
            )
        open_edx_user.has_been_synced = True
        open_edx_user.save()
        return True


def reconcile_edx_username(user):
    """
    Reconcile the user's edX username.

    If the user doesn't have an edX username, then we should use the user's
    supplied username if it exists. If they don't have a username either, then
    we should generate it.

    Args:
    - user: the user to reconcile
    Returns:
    - boolean, true if we created a username
    """

    if not user.openedx_users.filter(edx_username__isnull=False).exists():
        edx_user, _ = OpenEdxUser.objects.filter(
            edx_username__isnull=True, user=user
        ).get_or_create(defaults={"user": user})

        # skip the user's username if it's an email address or has a @ in it
        # @ is disallowed in edx usernames so instead force it through usernameify
        user_username = (
            None
            if "@" in user.username or user.username == user.email
            else user.username
        )

        edx_user.edx_username = (
            user_username[:OPENEDX_USERNAME_MAX_LEN]
            if user_username
            else usernameify(user.name, user.email, OPENEDX_USERNAME_MAX_LEN)
        )
        edx_user.save()
        return True

    return False


@transaction.atomic
def create_edx_auth_token(user):
    """
    Creates refresh token for LMS for the user

    Args:
        user(user.models.User): the user to create the record for

    Returns:
        openedx.models.OpenEdXAuth: auth model with refresh_token populated
    """

    # In order to acquire auth tokens from Open edX we need to perform the following steps:
    #
    # 1. Create a persistent session so that state is retained like a browser
    # 2. Initialize a session cookie for xPro, this emulates a user login
    # 3. Initiate an Open edX login, delegates to xPro using the session cookie
    # 4. Initiate an Open edX OAuth2 authorization for xPro
    # 5. Redirects back to xPro with the access token
    # 6. Redeem access token for a refresh/access token pair

    # if the user hasn't been created on openedx, we can't do any of this
    if not user.openedx_users.filter(
        edx_username__isnull=False, has_been_synced=True
    ).exists():
        return None

    # ensure only we can update this for the duration of the
    auth, _ = OpenEdxApiAuth.objects.select_for_update().get_or_create(user=user)

    # we locked on the previous operation and something else populated these values
    if auth.refresh_token and auth.access_token:
        return auth

    # Step 1
    with requests.Session() as req_session:
        # Step 2
        django_session = auth_api.create_user_session(user)
        session_cookie = requests.cookies.create_cookie(
            name=settings.SESSION_COOKIE_NAME,
            domain=urlparse(settings.SITE_BASE_URL).hostname,
            path=settings.SESSION_COOKIE_PATH,
            value=django_session.session_key,
        )
        req_session.cookies.set_cookie(session_cookie)

        # Step 3
        url = edx_url(OPENEDX_SOCIAL_LOGIN_PATH)
        resp = req_session.get(url)
        resp.raise_for_status()

        # Step 4
        redirect_uri = urljoin(
            settings.SITE_BASE_URL, reverse(OPENEDX_AUTH_COMPLETE_URL)
        )
        url = edx_url(OPENEDX_OAUTH2_AUTHORIZE_PATH)
        params = dict(  # noqa: C408
            client_id=settings.OPENEDX_API_CLIENT_ID,
            scope=" ".join(OPENEDX_OAUTH2_SCOPES),
            redirect_uri=redirect_uri,
            response_type="code",
        )
        resp = req_session.get(url, params=params)
        resp.raise_for_status()

        # Step 5
        if not resp.url.startswith(redirect_uri):
            raise OpenEdXOAuth2Error(
                f"Redirected to '{resp.url}', expected: '{redirect_uri}'"  # noqa: EM102
            )
        qs = parse_qs(urlparse(resp.url).query)
        if not qs.get(OPENEDX_OAUTH2_ACCESS_TOKEN_PARAM):
            raise OpenEdXOAuth2Error("Did not receive access_token from Open edX")  # noqa: EM101

        # Step 6
        auth = _create_tokens_and_update_auth(
            auth,
            dict(  # noqa: C408
                code=qs[OPENEDX_OAUTH2_ACCESS_TOKEN_PARAM],
                grant_type="authorization_code",
                client_id=settings.OPENEDX_API_CLIENT_ID,
                client_secret=settings.OPENEDX_API_CLIENT_SECRET,
                redirect_uri=redirect_uri,
            ),
        )

    return auth  # noqa: RET504


def update_edx_user_profile(user):
    """
    Updates the specified user's profile in edX. This only changes a handful of
    fields; it's mostly for syncing demographic data.

    Args:
        user(user.models.User): the user to update
    """
    auth = get_valid_edx_api_auth(user)
    req_session = requests.Session()
    resp = req_session.patch(
        edx_url(urljoin(OPENEDX_UPDATE_USER_PATH, user.edx_username)),
        json=dict(  # noqa: C408
            name=user.name,
            country=user.legal_address.country if user.legal_address else None,
            state=user.legal_address.edx_us_state if user.legal_address else None,
            gender=user.user_profile.edx_gender if user.user_profile else None,
            year_of_birth=(
                user.user_profile.year_of_birth if user.user_profile else None
            ),
            level_of_education=(
                user.user_profile.level_of_education if user.user_profile else None
            ),
        ),
        headers={
            "Authorization": f"Bearer {auth.access_token}",
            "Content-Type": "application/merge-patch+json",
        },
    )

    # edX responds with 200 on success, not 201
    if resp.status_code != status.HTTP_200_OK:
        raise EdxApiUserUpdateError(
            f"Error updating Open edX user. {get_error_response_summary(resp)}"  # noqa: EM102
        )


def update_edx_user_email(user):
    """
    Updates the LMS email address for the user with the user's current email address
    utilizing the social auth (oauth) mechanism.

    Args:
        user(user.models.User): the user to update the record for
    """
    with requests.Session() as req_session:
        django_session = auth_api.create_user_session(user)
        session_cookie = requests.cookies.create_cookie(
            name=settings.SESSION_COOKIE_NAME,
            domain=urlparse(settings.SITE_BASE_URL).hostname,
            path=settings.SESSION_COOKIE_PATH,
            value=django_session.session_key,
        )
        req_session.cookies.set_cookie(session_cookie)

        url = edx_url(OPENEDX_SOCIAL_LOGIN_PATH)
        resp = req_session.get(url)
        resp.raise_for_status()

        redirect_uri = urljoin(
            settings.SITE_BASE_URL, reverse(OPENEDX_AUTH_COMPLETE_URL)
        )
        url = edx_url(OPENEDX_OAUTH2_AUTHORIZE_PATH)
        params = dict(  # noqa: C408
            client_id=settings.OPENEDX_API_CLIENT_ID,
            scope=" ".join(OPENEDX_OAUTH2_SCOPES),
            redirect_uri=redirect_uri,
            response_type="code",
        )
        resp = req_session.get(url, params=params)
        resp.raise_for_status()


def _create_tokens_and_update_auth(auth, params):
    """
    Updates an OpenEdxApiAuth given the passed params

    Args:
        auth (openedx.models.OpenEdxApiAuth): the api auth credentials to update with the given params
        params (dict): the params to pass to the access token endpoint

    Returns:
        openedx.models.OpenEdxApiAuth:
            the updated auth records
    """
    resp = requests.post(edx_url(OPENEDX_OAUTH2_ACCESS_TOKEN_PATH), data=params)  # noqa: S113
    resp.raise_for_status()

    result = resp.json()

    # artificially reduce the expiry window since to cover
    expires_in = (
        result["expires_in"] - OPENEDX_OAUTH2_ACCESS_TOKEN_EXPIRY_MARGIN_SECONDS
    )

    auth.refresh_token = result["refresh_token"]
    auth.access_token = result["access_token"]
    auth.access_token_expires_on = now_in_utc() + timedelta(seconds=expires_in)
    auth.save()
    return auth


def repair_faulty_edx_user(user):
    """
    Loops through all Users that are incorrectly configured in edX and attempts to get
    them in the correct state.

    Args:
        user (User): User to repair
        platform (str): The openedx platform

    Returns:
        (bool, bool): Flags indicating whether a new edX user was created and whether a new
                edX auth token was created.
    """
    created_user, created_auth_token = False, False
    try:
        created_user = create_edx_user(user)
    except Exception as e:
        # 409 means we have a username conflict - pass in that case so we can
        # try to create the api auth tokens; re-raise otherwise

        if "code: 409" in str(e):
            pass
        else:
            raise Exception from e  # noqa: TRY002

    if not hasattr(user, "openedx_api_auth"):
        create_edx_auth_token(user)
        created_auth_token = True

        if (
            find_object_with_matching_attr(
                user.openedx_users.all(), "platform", value=PLATFORM_EDX
            )
            is None
        ):
            # if we could create an auth token, then this user's just disconnected for some reason
            # so go ahead and create the OpenEdxUser record for them (if there isn't one)
            (edx_user, forced_create) = user.openedx_users.get_or_create()
            edx_user.save()

    return created_user, created_auth_token


def repair_faulty_openedx_users():
    """
    Loops through all Users that are incorrectly configured with the openedx and attempts to get
    them in the correct state.

    Returns:
        list of User: Users that were successfully repaired
    """
    now = now_in_utc()
    repaired_users = []
    for user in User.faulty_openedx_users.filter(
        created_on__lt=now - timedelta(minutes=OPENEDX_REPAIR_GRACE_PERIOD_MINS)
    ):
        try:
            # edX is our only openedx for the time being. If a different openedx is added, this
            # function will need to be updated.
            created_user, created_auth_token = repair_faulty_edx_user(user)
        except HTTPError as exc:  # noqa: PERF203
            log.exception(
                "Failed to repair faulty user %s (%s). %s",
                user.edx_username,
                user.email,
                get_error_response_summary(exc.response),
            )
        except Exception:  # pylint: disable=broad-except
            log.exception(
                "Failed to repair faulty user %s (%s)", user.edx_username, user.email
            )
        else:
            if created_user or created_auth_token:
                repaired_users.append(user)
    return repaired_users


def get_valid_edx_api_auth(user, ttl_in_seconds=OPENEDX_AUTH_DEFAULT_TTL_IN_SECONDS):
    """
    Returns a valid api auth, possibly refreshing the tokens

    Args:
        user (users.models.User): the user to get an auth for
        ttl_in_seconds (int): how long the auth credentials need to remain
                              unexpired without needing a refresh (in seconds)

    Returns:
        auth:
            updated OpenEdxApiAuth
    """
    assert (  # noqa: S101
        ttl_in_seconds < OPENEDX_AUTH_MAX_TTL_IN_SECONDS
    ), f"ttl_in_seconds must be less than {OPENEDX_AUTH_MAX_TTL_IN_SECONDS}"

    expires_after = now_in_utc() + timedelta(seconds=ttl_in_seconds)
    auth = OpenEdxApiAuth.objects.filter(
        user=user, access_token_expires_on__gt=expires_after
    ).first()
    if not auth:
        # if the auth was no longer valid, try to update it
        with transaction.atomic():
            auth = OpenEdxApiAuth.objects.select_for_update().get(user=user)
            # check again once we have an exclusive lock, something else may have refreshed it for us
            if auth.access_token_expires_on > expires_after:
                return auth
            # it's still invalid, so refresh it now
            return _refresh_edx_api_auth(auth)
    # got a valid auth on first attempt
    return auth


def _refresh_edx_api_auth(auth):
    """
    Updates the api tokens for the given auth

    Args:
        auth (openedx.models.OpenEdxApiAuth): the auth to update

    Returns:
        auth:
            updated OpenEdxApiAuth
    """
    # Note: this is subject to thundering herd problems, we should address this at some point
    return _create_tokens_and_update_auth(
        auth,
        dict(  # noqa: C408
            refresh_token=auth.refresh_token,
            grant_type="refresh_token",
            client_id=settings.OPENEDX_API_CLIENT_ID,
            client_secret=settings.OPENEDX_API_CLIENT_SECRET,
        ),
    )


def get_edx_api_client(user, ttl_in_seconds=OPENEDX_AUTH_DEFAULT_TTL_IN_SECONDS):
    """
    Gets an edx api client instance for the user

    Args:
        user (users.models.User): A user object
        ttl_in_seconds (int): number of seconds the auth credentials for this client should still be valid

    Returns:
         EdxApi: edx api client instance
    """
    try:
        auth = get_valid_edx_api_auth(user, ttl_in_seconds=ttl_in_seconds)
    except OpenEdxApiAuth.DoesNotExist:
        raise NoEdxApiAuthError(f"{user!s} does not have an associated OpenEdxApiAuth")  # noqa: B904, EM102
    return EdxApi(
        {"access_token": auth.access_token},
        settings.OPENEDX_API_BASE_URL,
        timeout=settings.EDX_API_CLIENT_TIMEOUT,
    )


def get_edx_api_service_client():
    """
    Gets an edx api client instance for the service worker user

    Returns:
         EdxApi: edx api service worker client instance
    """
    if settings.OPENEDX_SERVICE_WORKER_API_TOKEN is None:
        raise ImproperlyConfigured("OPENEDX_SERVICE_WORKER_API_TOKEN is not set")  # noqa: EM101

    edx_client = EdxApi(
        {"access_token": settings.OPENEDX_SERVICE_WORKER_API_TOKEN},
        settings.OPENEDX_API_BASE_URL,
        timeout=settings.EDX_API_CLIENT_TIMEOUT,
    )

    return edx_client  # noqa: RET504


def get_edx_api_jwt_client(
    client_id: str = settings.OPENEDX_API_CLIENT_ID,
    client_secret: str = settings.OPENEDX_API_CLIENT_SECRET,
    *,
    use_studio: bool = False,
) -> EdxApi:
    """
    Gets a JWT for the specified client ID, then return an edX API client that
    uses the JWT.

    Some APIs require a JWT, including user retirement and course management.
    If you need to use a specific client ID for the client, you can specify that.
    Otherwise, it will use the default OAuth2 client ID and secret, which is
    usually mitxonline-oauth-app usually.

    The JWT APIs may _require_ that there's an edX user associated with the OAuth2
    client. If your client doesn't have that, your API calls will likely fail.

    If you need to hit the Studio API (ex. for course creation), make sure you
    set settings.OPENEDX_STUDIO_API_BASE_URL and set the use_studio flag.

    Args:
    - client_id (str): the client ID to authenticate as
    - client_secret (str): the client secret to use for authentication
    Keyword Args:
    - use_studio (bool): Use the Studio API after getting the JWT.
    Returns:
    - EdxApi, with the JWT token in it for the user specified.
    """

    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "token_type": "jwt",
    }
    resp = requests.post(edx_url(OPENEDX_OAUTH2_ACCESS_TOKEN_PATH), data=data)  # noqa: S113
    resp.raise_for_status()
    access_token = resp.json()["access_token"]

    edx_client = EdxApi(
        {
            "access_token": access_token,
        },
        settings.OPENEDX_API_BASE_URL
        if not use_studio or not settings.OPENEDX_STUDIO_API_BASE_URL
        else settings.OPENEDX_STUDIO_API_BASE_URL,
        timeout=settings.EDX_API_CLIENT_TIMEOUT,
    )

    return edx_client  # noqa: RET504


def get_edx_retirement_service_client():
    """
    Generates a JWT access token for the retirement service worker and returns the edX api client.
    """
    if not settings.OPENEDX_RETIREMENT_SERVICE_WORKER_CLIENT_ID:
        raise ImproperlyConfigured(
            "OPENEDX_RETIREMENT_SERVICE_WORKER_CLIENT_ID is not set"  # noqa: EM101
        )
    elif not settings.OPENEDX_RETIREMENT_SERVICE_WORKER_CLIENT_SECRET:
        raise ImproperlyConfigured(
            "OPENEDX_RETIREMENT_SERVICE_WORKER_CLIENT_SECRET is not set"  # noqa: EM101
        )

    return get_edx_api_jwt_client(
        settings.OPENEDX_RETIREMENT_SERVICE_WORKER_CLIENT_ID,
        settings.OPENEDX_RETIREMENT_SERVICE_WORKER_CLIENT_SECRET,
    )


def get_edx_course_management_service_client():
    """
    Generate an edX API client for course management.

    Set a specific client ID/secret for this by setting OPENEDX_COURSES_SERVICE_WORKER_CLIENT_ID
    and OPENEDX_COURSES_SERVICE_WORKER_CLIENT_SECRET in settings. Otherwise, this
    will default to using the OPENEDX_API_CLIENT_ID.
    """

    if not settings.OPENEDX_COURSES_SERVICE_WORKER_CLIENT_ID:
        raise ImproperlyConfigured(
            "OPENEDX_COURSES_SERVICE_WORKER_CLIENT_ID is not set"  # noqa: EM101
        )
    elif not settings.OPENEDX_COURSES_SERVICE_WORKER_CLIENT_SECRET:
        raise ImproperlyConfigured(
            "OPENEDX_COURSES_SERVICE_WORKER_CLIENT_SECRET is not set"  # noqa: EM101
        )

    return get_edx_api_jwt_client(
        settings.OPENEDX_COURSES_SERVICE_WORKER_CLIENT_ID,
        settings.OPENEDX_COURSES_SERVICE_WORKER_CLIENT_SECRET,
        use_studio=True,
    )


def get_edx_api_course_detail_client():
    """
    Gets an edx api client instance for use with the grades api

    Returns:
        CourseDetails: edx api course client instance
    """
    edx_client = get_edx_api_service_client()
    return edx_client.course_detail


def get_edx_api_course_mode_client():
    """
    Gets an edx api client instance for use with the grades api

    Returns:
        CourseDetails: edx api course client instance
    """
    edx_client = get_edx_api_service_client()
    return edx_client.course_mode


def get_edx_api_grades_client():
    """
    Gets an edx api client instance for use with the grades api

    Returns:
        UserCurrentGrades: edx api grades client instance
    """
    edx_client = get_edx_api_service_client()
    return edx_client.current_grades


def get_edx_grades_with_users(course_run, user=None):
    """
    Get all current grades for a course run from OpenEdX along with the enrolled user object

    Args:
        course_run (CourseRun): The course run for which to fetch the grades and users
        user (users.models.User): Limit the grades to this user

    Returns:
        List of (UserCurrentGrade, User) tuples
    """
    grades_client = get_edx_api_grades_client()
    if user:
        edx_grade = grades_client.get_student_current_grade(
            user.edx_username, course_run.courseware_id
        )
        yield edx_grade, user
    else:
        edx_course_grades = grades_client.get_course_current_grades(
            course_run.courseware_id
        )
        all_grades = list(edx_course_grades.all_current_grades)
        for edx_grade in all_grades:
            try:
                user = User.objects.get(openedx_users__edx_username=edx_grade.username)
            except User.DoesNotExist:  # noqa: PERF203
                log.warning("User with username %s not found", edx_grade.username)
            else:
                yield edx_grade, user


def existing_edx_enrollment(user, course_id, mode, is_active=True):  # noqa: FBT002
    """
    Returns enrollment object if user is already enrolled in edx course run.

    Args:
        user (users.models.User): The user to enroll
        courseware_id : The course runs to enroll in
        mode (str): The course mode to enroll the user with
        is_active (boolean): Whether the expected course run enrollment is active.

    Returns:
        (edx_api.enrollments.models.Enrollment or None):
            The results of enrollments via the edx API client
    """
    edx_client = get_edx_api_service_client()
    edx_enrollments = edx_client.enrollments.get_enrollments(
        course_id=course_id, usernames=[user.edx_username]
    )
    for enrollment in edx_enrollments:
        if enrollment.mode == mode and enrollment.is_active == is_active:
            return enrollment
    return None


def enroll_in_edx_course_runs(
    user,
    course_runs,
    *,
    mode=EDX_DEFAULT_ENROLLMENT_MODE,
    force_enrollment=True,
):
    """
    Enrolls a user in edx course runs. If the user doesn't have a valid
    set of API credentials, this will try to regenerate them (unless told not to).

    Args:
        user (users.models.User): The user to enroll
        course_runs (iterable of CourseRun): The course runs to enroll in
        mode (str): The course mode to enroll the user with
        force_enrollment (bool): If True, Enforces Enrollment after the enrollment end date
                                    has been passed or upgrade_deadline is ended

    Returns:
        list of edx_api.enrollments.models.Enrollment:
            The results of enrollments via the edx API client

    Raises:
        EdxApiEnrollErrorException: Raised if the underlying edX API HTTP request fails
        UnknownEdxApiEnrollException: Raised if an unknown error was encountered during the edX API request
    """
    edx_client = get_edx_api_service_client()

    if reconcile_edx_username(user):
        user.refresh_from_db()

    username = user.edx_username

    results = []
    for course_run in course_runs:
        try:
            enrollment = existing_edx_enrollment(
                user, course_run.courseware_id, mode=mode
            )
            if enrollment is None:
                enrollment = edx_client.enrollments.create_student_enrollment(
                    course_run.courseware_id,
                    mode=mode,
                    username=username,
                    force_enrollment=force_enrollment,
                )
                if not enrollment.is_active:
                    enrollment = edx_client.enrollments.create_student_enrollment(
                        course_run.courseware_id,
                        mode=mode,
                        username=username,
                        force_enrollment=force_enrollment,
                    )
            results.append(enrollment)
        except HTTPError as exc:  # noqa: PERF203
            raise EdxApiEnrollErrorException(user, course_run, exc) from exc
        except EdxApiUserDoesNotExistError:
            log.warning(
                "User %s does not exist in edX, attempting to create user.",
                user.edx_username,
            )
            # If the user doesn't exist, we need to create them first
            try:
                created_user, _ = repair_faulty_edx_user(user)
                if created_user:
                    enrollment = edx_client.enrollments.create_student_enrollment(
                        course_run.courseware_id,
                        mode=mode,
                        username=username,
                        force_enrollment=force_enrollment,
                    )
                    results.append(enrollment)
            except Exception as exc:
                log.exception("Failed to create user %s in edX.", user.edx_username)
                raise UnknownEdxApiEnrollException(user, course_run, exc) from exc
        except Exception as exc:  # pylint: disable=broad-except
            raise UnknownEdxApiEnrollException(user, course_run, exc) from exc
    return results


def retry_failed_edx_enrollments():
    """
    Gathers all CourseRunEnrollments with edx_enrolled=False and retries them via the edX API

    Returns:
        list of CourseRunEnrollment: All CourseRunEnrollments that were successfully retried
    """
    now = now_in_utc()
    failed_run_enrollments = courses.models.CourseRunEnrollment.objects.select_related(
        "user", "run"
    ).filter(
        user__is_active=True,
        edx_enrolled=False,
        created_on__lt=now - timedelta(minutes=OPENEDX_REPAIR_GRACE_PERIOD_MINS),
    )
    succeeded = []
    for enrollment in failed_run_enrollments:
        user = enrollment.user
        course_run = enrollment.run
        try:
            enroll_in_edx_course_runs(
                user, [course_run], mode=enrollment.enrollment_mode
            )
        except Exception as exc:  # pylint: disable=broad-except
            log.exception(str(exc))  # noqa: TRY401
        else:
            enrollment.edx_enrolled = True
            enrollment.edx_emails_subscription = True
            enrollment.save_and_log(None)
            succeeded.append(enrollment)
    return succeeded


def unenroll_edx_course_run(run_enrollment):
    """
    Unenrolls/deactivates a user in an edx course run

    Args:
        run_enrollment (CourseRunEnrollment): The enrollment record that represents the
            currently-enrolled course run

    Returns:
        edx_api.enrollments.models.Enrollment:
            The resulting Enrollment object (which should be set to inactive)

    Raises:
        EdxApiEnrollErrorException: Raised if the underlying edX API HTTP request fails
        UnknownEdxApiEnrollException: Raised if an unknown error was encountered during the edX API request
    """
    edx_client = get_edx_api_service_client()
    try:
        deactivated_enrollment = edx_client.enrollments.deactivate_enrollment(
            run_enrollment.run.courseware_id, username=run_enrollment.user.edx_username
        )
    except HTTPError as exc:
        raise EdxApiEnrollErrorException(run_enrollment.user, run_enrollment.run, exc)  # noqa: B904
    except Exception as exc:  # pylint: disable=broad-except  # noqa: BLE001
        raise UnknownEdxApiEnrollException(run_enrollment.user, run_enrollment.run, exc)  # noqa: B904
    else:
        return deactivated_enrollment


def update_edx_user_name(user):
    """
    Makes a request to update user's name on edx if changed in MITx Online

    Args:
        user (user.models.User): the application user

    Returns:
        edx_api.user_info.models.Info: Object representing updated details of user in edX

    Raises:
        UserNameUpdateFailedException: Raised if underlying edX API request fails due to any reason
    """

    edx_client = get_edx_api_client(user)
    try:
        return edx_client.user_info.update_user_name(user.edx_username, user.name)
    except Exception as exc:  # noqa: BLE001
        raise UserNameUpdateFailedException(  # noqa: B904
            "Error updating user's full name in edX.",  # noqa: EM101
            exc,
        )


def sync_enrollments_with_edx(
    user: User,
) -> SyncResult[courses.models.CourseRunEnrollment]:
    """Syncs enrollment records so that local enrollments match the enrollment data in edX"""
    client = get_edx_api_client(user)
    edx_enrollments = client.enrollments.get_student_enrollments()
    local_enrollments = (
        user.courserunenrollment_set(manager="all_objects")
        .filter(user=user)
        .exclude(run__courseware_id=None)
        .order_by("run__courseware_id")
        .all()
    )
    local_enrollments_map = {
        enrollment.run.courseware_id: enrollment for enrollment in local_enrollments
    }
    local_only_ids, common_ids, edx_only_ids = get_partitioned_set_difference(
        set(local_enrollments_map.keys()), set(edx_enrollments.enrollments.keys())
    )
    results = SyncResult()
    # Sync active status for local enrollments that have an equivalent enrollment in edX
    for courseware_id in common_ids:
        edx_enrollment = edx_enrollments.enrollments[courseware_id]
        local_enrollment = local_enrollments_map[courseware_id]
        if local_enrollment.active and not edx_enrollment.is_active:
            local_enrollment.deactivate_and_save(
                change_status=ENROLL_CHANGE_STATUS_UNENROLLED
            )
            results.deactivated.append(local_enrollment)
        elif not local_enrollment.active and edx_enrollment.is_active:
            local_enrollment.reactivate_and_save()
            results.reactivated.append(local_enrollment)
    # Create enrollment records for any enrollments that exist in edX but not locally
    if edx_only_ids:
        run_values_list = courses.models.CourseRun.objects.filter(
            courseware_id__in=edx_only_ids
        ).values("id", "courseware_id")
        for run_values in run_values_list:
            local_enrollment = user.courserunenrollment_set.create(
                user=user,
                run_id=run_values["id"],
                edx_enrolled=True,
                active=edx_enrollments.enrollments[
                    run_values["courseware_id"]
                ].is_active,
            )
            results.created.append(local_enrollment)

    # Confirm if local_only_ids are actually active enrollments before logging these as error
    local_only_active_ids = (
        user.courserunenrollment_set(manager="all_objects")
        .filter(user=user, run__courseware_id__in=local_only_ids, active=True)
        .values_list("run__courseware_id", flat=True)
    )
    # Log an error if any enrollments exist locally but not in edX
    if local_only_active_ids:
        log.error(
            "Found local enrollments with no equivalent enrollment in edX for User - %s (CourseRunEnrollment ids: %s)",
            user.edx_username,
            str(local_only_active_ids),
        )
    return results


def subscribe_to_edx_course_emails(user, course_run):
    """
    Subscribes a user to course emails in edX

    Args:
        user (users.models.User): The user that will be subscribed
        course_run (CourseRun): The course runs to subscribe to

    Returns:
        boolean:
            either subscribed successfully or not

    Raises:
        EdxApiEmailSettingsErrorException: Raised if the underlying edX API HTTP request fails
        EdxApiChangeEmailSettingsException: Raised if an unknown error was encountered during the edX API request
    """
    edx_client = get_edx_api_client(user)
    try:
        result = edx_client.email_settings.subscribe(course_run.courseware_id)
    except HTTPError as exc:
        raise EdxApiEmailSettingsErrorException(user, course_run, exc) from exc
    except Exception as exc:
        raise UnknownEdxApiEmailSettingsException(user, course_run, exc) from exc
    return result


def unsubscribe_from_edx_course_emails(user, course_run):
    """
    Unsubscribes a user from an edX course

    Args:
        user (users.models.User): The user to unsubscribe
        course_run (CourseRun): The enrolled course run

    Returns:
        boolean:
            either unsubscribed successfully or not

    Raises:
        EdxApiEmailSettingsErrorException: Raised if the underlying edX API HTTP request fails
        EdxApiChangeEmailSettingsException: Raised if an unknown error was encountered during the edX API request
    """
    edx_client = get_edx_api_client(user)
    try:
        result = edx_client.email_settings.unsubscribe(course_run.courseware_id)
    except HTTPError as exc:
        raise EdxApiEmailSettingsErrorException(user, course_run, exc) from exc
    except Exception as exc:
        raise UnknownEdxApiEmailSettingsException(user, course_run, exc) from exc
    return result


def validate_username_email_with_edx(edx_username, email):
    """
    Returns validation message after validating it with edX.

    Args:
        edx_username (str): the username in edx
        email (str): the email

    Raises:
        EdxApiRegistrationValidationException: Raised if response status is not OK.
    """

    req_session = requests.Session()
    req_session.headers.update(
        {ACCESS_TOKEN_HEADER_NAME: settings.MITX_ONLINE_REGISTRATION_ACCESS_TOKEN}
    )
    resp = req_session.post(
        edx_url(OPENEDX_REGISTRATION_VALIDATION_PATH),
        data=dict(  # noqa: C408
            username=edx_username,
            email=email,
        ),
    )
    if resp.status_code != status.HTTP_200_OK:
        raise EdxApiRegistrationValidationException(edx_username, resp)
    result = resp.json()
    return result["validation_decisions"]


def bulk_retire_edx_users(edx_usernames):
    """
    Bulk retires edX users.

    This method calls edX bulk retirement API to initiate the user retirement on edX.
    Users will be moved to the pending retirement state and then retirement will be carried out by our
    tubular concourse pipeline.

    Args:
        edx_usernames (str): Comma separated usernames
    """
    edx_client = get_edx_retirement_service_client()
    response = edx_client.bulk_user_retirement.retire_users(
        {"usernames": edx_usernames}
    )
    return response  # noqa: RET504


def get_edx_course(course_id: str, *, client: EdxApi | None = None) -> CourseRun:
    """
    Get information about a course from edX.

    Args:
    - course_id (str): the readable ID for the course run.
    Keyword Args:
    - client (EdxApi): edX client (if you want to reuse one)
    Returns:
    - edx_api.course_runs.models.CourseRun: the course run details
    """

    edx_client = client if client else get_edx_course_management_service_client()

    return edx_client.course_runs.get_course_run(course_id)


def get_edx_course_list(
    page_url: str | None = None, *, client: EdxApi | None = None
) -> CourseRunList:
    """
    Get the paginated list of course runs from edX.

    Args:
    - page_url (str): The page to retreive. This is part of the CourseRunList object.
    Keyword Args:
    - client (EdxApi): edX client (if you want to reuse one)
    Returns:
    - edx_api.course_runs.models.CourseRunList: paginated list of course runs
    """

    edx_client = client if client else get_edx_course_management_service_client()

    return edx_client.course_runs.get_course_runs_list(page_url)


def clone_edx_course(
    existing_course_id: str, new_course_id: str, *, client: EdxApi | None = None
) -> CourseRun | bool:
    """
    Clone an edX course run.

    Args:
    - existing_course_id: the readable ID of the course to use as the base
    - new_course_id: the readable ID of the new course
    Keyword Args:
    - client (EdxApi): edX client (if you want to reuse one)
    Returns:
    - bool or edx_api.course_runs.models.CourseRun: the new course run details, or
      False if an error occurred
    """

    edx_client = client if client else get_edx_course_management_service_client()

    resp = edx_client.course_runs.clone_course_run(existing_course_id, new_course_id)

    if resp.ok:
        return get_edx_course(new_course_id)

    return False


def create_edx_course(  # noqa: PLR0913
    org: str,
    number: str,
    run: str,
    title: str,
    pacing_type: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    enrollment_start: datetime | None = None,
    enrollment_end: datetime | None = None,
    *,
    client: EdxApi | None = None,
) -> CourseRun:
    """
    Create a new, blank edX course run.

    Args:
    - org (str): Organization for the new course run.
    - number (str): Course number for the new course run. (Without 'course-v1')
    - run (str): The run id for the new course run.
    - title (str): The title of the new course run.
    - pacing_type (str, optional): The pacing type for the new course run. Defaults to None.
    - start (datetime, optional): The start date for the new course run. Defaults to None.
    - end (datetime, optional): The end date for the new course run. Defaults to None.
    - enrollment_start (datetime, optional): The enrollment start date for the new course run. Defaults to None.
    - enrollment_end (datetime, optional): The enrollment end date for the new course run. Defaults to None.
    Keyword Args:
    - client (EdxApi): edX client (if you want to reuse one)
    Returns:
    - edx_api.course_runs.models.CourseRun: the course run details
    """

    edx_client = client if client else get_edx_course_management_service_client()

    return edx_client.course_runs.create_course_run(
        org,
        number,
        run,
        title,
        pacing_type,
        start,
        end,
        enrollment_start,
        enrollment_end,
    )


def update_edx_course(  # noqa: PLR0913
    course_id: str,
    title: str | None = None,
    pacing_type: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    enrollment_start: datetime | None = None,
    enrollment_end: datetime | None = None,
    *,
    client: EdxApi | None = None,
) -> CourseRun:
    """
    Update an existing edX course run.

    Args:
    - course_id (str): The readable ID of the course run to edit.
    - title (str): The title of the new course run.
    - pacing_type (str, optional): The pacing type for the new course run. Defaults to None.
    - start (datetime, optional): The start date for the new course run. Defaults to None.
    - end (datetime, optional): The end date for the new course run. Defaults to None.
    - enrollment_start (datetime, optional): The enrollment start date for the new course run. Defaults to None.
    - enrollment_end (datetime, optional): The enrollment end date for the new course run. Defaults to None.
    Keyword Args:
    - client (EdxApi): edX client (if you want to reuse one)
    Returns:
    - edx_api.course_runs.models.CourseRun: the course run details
    """
    edx_client = client if client else get_edx_course_management_service_client()

    return edx_client.course_runs.update_course_run(
        course_id, title, pacing_type, start, end, enrollment_start, enrollment_end
    )


def process_course_run_clone(target_id: int, *, base_id: int | str | None = None):
    """
    Clone a course run, using details from CourseRun objects in MITx Online.

    When we need a new course run (as a re-run or a special B2B course run), we
    create the CourseRun object in the system, and then we need to make the run
    in edX. This will assume there's a base course run that uses the readable ID
    of the underlying _Course_ record, and will clone that. Some of the data from
    the CourseRun will then be copied over into the newly cloned edX run (dates,
    etc.) and the URL will be backfilled into the CourseRun.

    If a different course run needs to be used as the base course, you can
    set that. Pass either the PK of the course or the readable ID. If a readable
    ID is passed, it will be supplied verbatim to the clone API. (In other words,
    it can be a course that MITx Online doesn't know about.)

    Args:
    - target_id (int): The PK of the target course (i.e. the one we're creating)
    - base_id (int|str): The PK or readable ID of the base course to clone.
    Returns:
    bool, whether or not it worked
    """
    edx_client = get_edx_api_jwt_client(
        settings.OPENEDX_COURSES_SERVICE_WORKER_CLIENT_ID,
        settings.OPENEDX_COURSES_SERVICE_WORKER_CLIENT_SECRET,
        use_studio=True,
    )

    target_course = courses.models.CourseRun.objects.get(pk=target_id)
    base_course = target_course.course.readable_id

    if base_id:
        if base_id is int:
            if courses.models.Course.objects.filter(pk=base_id).exists():
                base_course = courses.models.Course.objects.get(pk=base_id).readable_id
            elif courses.models.CourseRun.objects.filter(pk=base_id).exists():
                base_course = courses.models.CourseRun.objects.get(
                    pk=base_id
                ).readable_id
            else:
                msg = f"Specified base course {base_id} doesn't exist."
                raise ValueError(msg)
        else:
            base_course = str(base_id)

    get_edx_course(base_course, client=edx_client)

    try:
        get_edx_course(target_course.readable_id, client=edx_client)

        msg = f"Course ID {target_course.readable_id} was found in edX. Can't continue."
        raise ValueError(msg)
    except CourseRunAPIError:
        # An HTTP error is good in this case. We don't want the target course to exist.
        pass

    resp = clone_edx_course(base_course, target_course.readable_id, client=edx_client)

    if not resp:
        msg = f"Couldn't clone {base_course} to {target_course.readable_id}."
        raise ValueError(msg)

    # We should have the target course in edX now. We need to update it with the
    # data from our course run.

    course_params = [
        target_course.readable_id,
        target_course.title,
        "self_paced" if target_course.is_self_paced else "instructor_paced",
    ]

    # We can only specify the start and end dates if there are both of them.
    # And, we can only specify enrollment start/stop if there are both of them
    # and the course has start/end dates.

    if target_course.start_date and target_course.end_date:
        course_params.append(target_course.start_date)
        course_params.append(target_course.end_date)

        if target_course.enrollment_start and target_course.enrollment_end:
            course_params.append(target_course.enrollment_start)
            course_params.append(target_course.enrollment_end)

    resp = update_edx_course(
        *course_params,
        client=edx_client,
    )

    # Set the ingestion flag on the course run to True
    # All B2B courses should be flagged for content file ingestion - we can
    # toggle it off manually if necessary.
    # In the odd chance we don't have a page, trigger a warning.
    if target_course.course.page:
        target_course.course.page.ingest_content_files_for_ai = True
        target_course.course.save()
    else:
        log.warning(
            "Warning: processed course run clone for %s but can't set the ingestion flag because there's no CoursePage",
            target_course,
        )
