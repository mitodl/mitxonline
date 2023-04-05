"""Courseware API functions"""
import logging
from datetime import timedelta
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.shortcuts import reverse
from edx_api.client import EdxApi
from mitol.common.utils import (
    find_object_with_matching_attr,
    get_error_response_summary,
    is_json_response,
    now_in_utc,
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
    EDX_ENROLLMENT_AUDIT_MODE,
    EDX_ENROLLMENT_VERIFIED_MODE,
    OPENEDX_REPAIR_GRACE_PERIOD_MINS,
    PLATFORM_EDX,
    PRO_ENROLL_MODE_ERROR_TEXTS,
)
from openedx.exceptions import (
    EdxApiEmailSettingsErrorException,
    EdxApiEnrollErrorException,
    EdxApiRegistrationValidationException,
    NoEdxApiAuthError,
    OpenEdXOAuth2Error,
    OpenEdxUserCreateError,
    UnknownEdxApiEmailSettingsException,
    UnknownEdxApiEnrollException,
    UserNameUpdateFailedException,
)
from openedx.models import OpenEdxApiAuth, OpenEdxUser
from openedx.tasks import regenerate_openedx_auth_tokens
from openedx.utils import SyncResult, edx_url
from users.api import fetch_user

log = logging.getLogger(__name__)
User = get_user_model()

OPENEDX_REGISTER_USER_PATH = "/user_api/v1/account/registration/"
OPENEDX_REGISTRATION_VALIDATION_PATH = "/api/user/v1/validation/registration"
OPENEDX_REQUEST_DEFAULTS = dict(country="US", honor_code=True)

OPENEDX_SOCIAL_LOGIN_XPRO_PATH = "/auth/login/mitxpro-oauth2/?auth_entry=login"
OPENEDX_OAUTH2_AUTHORIZE_PATH = "/oauth2/authorize"
OPENEDX_OAUTH2_ACCESS_TOKEN_PATH = "/oauth2/access_token"
OPENEDX_OAUTH2_SCOPES = ["read", "write"]
OPENEDX_OAUTH2_ACCESS_TOKEN_PARAM = "code"
OPENEDX_OAUTH2_ACCESS_TOKEN_EXPIRY_MARGIN_SECONDS = 10

OPENEDX_AUTH_DEFAULT_TTL_IN_SECONDS = 60
OPENEDX_AUTH_MAX_TTL_IN_SECONDS = 60 * 60

ACCESS_TOKEN_HEADER_NAME = "X-Access-Token"


def create_user(user):
    """
    Creates a user and any related artifacts in the openedx

    Args:
        user (user.models.User): the application user
    """
    create_edx_user(user)
    create_edx_auth_token(user)


def create_edx_user(user):
    """
    Makes a request to create an equivalent user in Open edX

    Args:
        user (user.models.User): the application user
    """
    application = Application.objects.get(name=settings.OPENEDX_OAUTH_APP_NAME)
    expiry_date = now_in_utc() + timedelta(hours=settings.OPENEDX_TOKEN_EXPIRES_HOURS)
    access_token = AccessToken.objects.create(
        user=user, application=application, token=generate_token(), expires=expiry_date
    )

    with transaction.atomic():
        open_edx_user, created = OpenEdxUser.objects.select_for_update().get_or_create(
            user=user, platform=PLATFORM_EDX
        )

        if not created and open_edx_user.has_been_synced:
            # Here we should check with edx that the user exists on that end.
            try:
                client = get_edx_api_client(user)
                client.user_info.get_user_info()
            except:
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
                username=user.username,
                email=user.email,
                name=user.name,
                provider=settings.MITX_ONLINE_OAUTH_PROVIDER,
                access_token=access_token.token,
                **OPENEDX_REQUEST_DEFAULTS,
            ),
        )
        # edX responds with 200 on success, not 201
        if resp.status_code != status.HTTP_200_OK:
            raise OpenEdxUserCreateError(
                f"Error creating Open edX user. {get_error_response_summary(resp)}"
            )
        open_edx_user.has_been_synced = True
        open_edx_user.save()
        return True


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
        url = edx_url(OPENEDX_SOCIAL_LOGIN_XPRO_PATH)
        resp = req_session.get(url)
        resp.raise_for_status()

        # Step 4
        redirect_uri = urljoin(
            settings.SITE_BASE_URL, reverse("openedx-private-oauth-complete")
        )
        url = edx_url(OPENEDX_OAUTH2_AUTHORIZE_PATH)
        params = dict(
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
                f"Redirected to '{resp.url}', expected: '{redirect_uri}'"
            )
        qs = parse_qs(urlparse(resp.url).query)
        if not qs.get(OPENEDX_OAUTH2_ACCESS_TOKEN_PARAM):
            raise OpenEdXOAuth2Error("Did not receive access_token from Open edX")

        # Step 6
        auth = _create_tokens_and_update_auth(
            auth,
            dict(
                code=qs[OPENEDX_OAUTH2_ACCESS_TOKEN_PARAM],
                grant_type="authorization_code",
                client_id=settings.OPENEDX_API_CLIENT_ID,
                client_secret=settings.OPENEDX_API_CLIENT_SECRET,
                redirect_uri=redirect_uri,
            ),
        )

    return auth


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

        url = edx_url(OPENEDX_SOCIAL_LOGIN_XPRO_PATH)
        resp = req_session.get(url)
        resp.raise_for_status()

        redirect_uri = urljoin(
            settings.SITE_BASE_URL, reverse("openedx-private-oauth-complete")
        )
        url = edx_url(OPENEDX_OAUTH2_AUTHORIZE_PATH)
        params = dict(
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
    resp = requests.post(edx_url(OPENEDX_OAUTH2_ACCESS_TOKEN_PATH), data=params)
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
            raise Exception from e

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
        except HTTPError as exc:
            log.exception(
                "Failed to repair faulty user %s (%s). %s",
                user.username,
                user.email,
                get_error_response_summary(exc.response),
            )
        except Exception:  # pylint: disable=broad-except
            log.exception(
                "Failed to repair faulty user %s (%s)", user.username, user.email
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
    assert (
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
        dict(
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
        raise NoEdxApiAuthError(
            "{} does not have an associated OpenEdxApiAuth".format(str(user))
        )
    return EdxApi(
        {"access_token": auth.access_token, "api_key": settings.OPENEDX_API_KEY},
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
        raise ImproperlyConfigured("OPENEDX_SERVICE_WORKER_API_TOKEN is not set")

    edx_client = EdxApi(
        {
            "access_token": settings.OPENEDX_SERVICE_WORKER_API_TOKEN,
            "api_key": settings.OPENEDX_API_KEY,
        },
        settings.OPENEDX_API_BASE_URL,
        timeout=settings.EDX_API_CLIENT_TIMEOUT,
    )

    return edx_client


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
            user.username, course_run.courseware_id
        )
        yield edx_grade, user
    else:
        edx_course_grades = grades_client.get_course_current_grades(
            course_run.courseware_id
        )
        all_grades = list(edx_course_grades.all_current_grades)
        for edx_grade in all_grades:
            try:
                user = User.objects.get(username=edx_grade.username)
            except User.DoesNotExist:
                log.warning("User with username %s not found", edx_grade.username)
            else:
                yield edx_grade, user


def existing_edx_enrollment(user, course_id, mode, is_active=True):
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
        course_id=course_id, usernames=[user.username]
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
    force_enrollment=False,
    regen_auth_tokens=True,
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
        regen_auth_token (bool): Regenerate the auth tokens if the learner's are invalid

    Returns:
        list of edx_api.enrollments.models.Enrollment:
            The results of enrollments via the edx API client

    Raises:
        EdxApiEnrollErrorException: Raised if the underlying edX API HTTP request fails
        UnknownEdxApiEnrollException: Raised if an unknown error was encountered during the edX API request
    """
    username = None
    if force_enrollment:
        edx_client = get_edx_api_service_client()
        username = user.username
    else:
        try:
            edx_client = get_edx_api_client(user)
        except (HTTPError, NoEdxApiAuthError) as exc:
            log.exception(
                "enroll_in_edx_course_runs got exception getting API client: %s %s",
                type(exc),
                exc,
            )

            if regen_auth_tokens and (
                "Bad Request" in str(exc) or type(exc) == NoEdxApiAuthError
            ):
                if OpenEdxApiAuth.objects.filter(user=user).count():
                    OpenEdxApiAuth.objects.filter(user=user).delete()
                    user.refresh_from_db()

                try:
                    log.exception(
                        "enroll_in_edx_course_runs: creating new auth tokens for %s",
                        user,
                    )
                    create_edx_auth_token(user)
                    user.refresh_from_db()
                    edx_client = get_edx_api_client(user)
                except Exception as auth_exc:
                    log.exception(
                        "enroll_in_edx_course_runs: got exception creating new auth token: %s",
                        auth_exc,
                    )
                    raise auth_exc
            elif not regen_auth_tokens and (
                "Bad Request" in str(exc) or type(exc) == NoEdxApiAuthError
            ):
                regenerate_openedx_auth_tokens.delay(user.id)
                raise exc
            else:
                raise exc

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
            results.append(enrollment)
        except HTTPError as exc:
            raise EdxApiEnrollErrorException(user, course_run, exc) from exc
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
            log.exception(str(exc))
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
    edx_client = get_edx_api_client(run_enrollment.user)
    try:
        deactivated_enrollment = edx_client.enrollments.deactivate_enrollment(
            run_enrollment.run.courseware_id
        )
    except HTTPError as exc:
        raise EdxApiEnrollErrorException(run_enrollment.user, run_enrollment.run, exc)
    except Exception as exc:  # pylint: disable=broad-except
        raise UnknownEdxApiEnrollException(run_enrollment.user, run_enrollment.run, exc)
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
        return edx_client.user_info.update_user_name(user.username, user.name)
    except Exception as exc:
        raise UserNameUpdateFailedException(
            "Error updating user's full name in edX.", exc
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
            user.username,
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


def validate_username_with_edx(username):
    """
    Returns validation message after validating it with edX.

    Args:
        username (str): the username

    Raises:
        EdxApiRegistrationValidationException: Raised if response status is not OK.
    """

    req_session = requests.Session()
    req_session.headers.update(
        {ACCESS_TOKEN_HEADER_NAME: settings.MITX_ONLINE_REGISTRATION_ACCESS_TOKEN}
    )
    resp = req_session.post(
        edx_url(OPENEDX_REGISTRATION_VALIDATION_PATH),
        data=dict(
            username=username,
        ),
    )
    if resp.status_code != status.HTTP_200_OK:
        raise EdxApiRegistrationValidationException(username, resp)
    result = resp.json()
    return result["validation_decisions"]["username"]
