"""Views for openedx"""

import logging

from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from oauth2_provider.contrib.rest_framework import OAuth2Authentication
from rest_framework import serializers, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    versioning_class,
)
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from courses.api import create_local_enrollment, generate_course_run_certificates
from courses.models import CourseRun, CourseRunAccessRole, CourseRunCertificate
from main.versioning import NoVersioning, V0Versioning
from openedx.api import (
    get_notification_preferences,
    update_notification_preference,
)
from openedx.constants import EDX_DEFAULT_ENROLLMENT_MODE, OPENEDX_COURSE_STAFF_ROLES
from openedx.exceptions import (
    EdxApiNotificationPreferencesError,
    NoEdxApiAuthError,
)
from openedx.serializers import NotificationPreferenceUpdateSerializer
from users.models import User

log = logging.getLogger(__name__)


def openedx_private_auth_complete(request):  # noqa: ARG001
    """Responds with a simple HTTP_200_OK"""
    # NOTE: this is only meant as a landing endpoint for api.create_edx_auth_token() flow
    return HttpResponse(status=status.HTTP_200_OK)


@extend_schema(exclude=True)
@api_view(["POST"])
@authentication_classes([OAuth2Authentication])
@permission_classes([IsAdminUser])
@versioning_class(NoVersioning)
def edx_enrollment_webhook(request):
    """
    Webhook endpoint that receives enrollment notifications from Open edX.

    When a user needs to be enrolled in a course (e.g., staff/instructor role added,
    or a course team manually enrolls learners from the instructor dashboard), the
    Open edX plugin POSTs to this endpoint so MITx Online can mirror the enrollment
    in the corresponding course run.

    A payload carrying a course staff "role" also records that role locally, so
    the dashboard can tell whether a user is on a run's course team. See
    CourseRunAccessRole.

    Authentication: OAuth2 Bearer token (Django OAuth Toolkit access token).

    Expected payload:
        {
            "email": "instructor@example.com",
            "course_id": "course-v1:MITx+1.001x+2025_T1",
            "role": "instructor",
            "mode": "audit"
        }

    Both "role" and "mode" are optional. "mode" defaults to the default edX
    enrollment mode when it is absent or empty.
    """
    # --- Validate payload ---
    email = request.data.get("email")
    course_id = request.data.get("course_id")
    role = request.data.get("role", "")
    requested_mode = request.data.get("mode")
    mode = requested_mode or EDX_DEFAULT_ENROLLMENT_MODE

    if not email or not course_id:
        return Response(
            {"error": "Missing required fields: email and course_id"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # --- Look up user ---
    try:
        user = User.objects.get(email__iexact=email)
    except User.DoesNotExist:
        log.warning(
            "Webhook: No user found with email %s for course %s (role: %s)",
            email,
            course_id,
            role,
        )
        return Response(
            {"error": "User not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    # --- Look up course run ---
    try:
        course_run = CourseRun.objects.get(courseware_id=course_id)
    except CourseRun.DoesNotExist:
        log.warning(
            "Webhook: No course run found with courseware_id %s (user: %s, role: %s)",
            course_id,
            email,
            role,
        )
        return Response(
            {"error": f"Course run with id {course_id} not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    # --- Record the course access role ---
    # Done before the enrollment so a role grant is never silently dropped by a
    # downstream enrollment failure; the two are independent facts.
    if role in OPENEDX_COURSE_STAFF_ROLES:
        _, role_created = CourseRunAccessRole.objects.get_or_create(
            user=user, run=course_run, role=role
        )
        log.info(
            "Webhook: Recorded course access role %s for user %s in course run %s (created: %s)",
            role,
            email,
            course_id,
            role_created,
        )
    elif role:
        # The success log below prints the role either way, which would read as
        # if it had been handled. Say so when it has not: a role arriving that
        # we do not record means the plugin's allowed-role setting and
        # OPENEDX_COURSE_STAFF_ROLES have drifted, or the casing differs.
        log.warning(
            "Webhook: Role %s for user %s in course run %s is not in "
            "OPENEDX_COURSE_STAFF_ROLES, so it was not recorded.",
            role,
            email,
            course_id,
        )

    # --- Create local enrollment ---
    # A payload carrying a role and no mode is a role grant rather than an
    # enrollment event, so it must not resurrect an enrollment somebody
    # deliberately deactivated. It still creates one when there is none: the
    # dashboard is built from enrollments, so without one a course admin has no
    # card to open, which is the whole reason the backfill exists.
    is_role_grant = bool(role) and requested_mode is None

    try:
        enrollment, created = create_local_enrollment(
            user, course_run, mode=mode, reactivate=not is_role_grant
        )
    except Exception:
        log.exception(
            "Webhook: Error creating enrollment for user %s in course run %s",
            email,
            course_id,
        )
        # Logged here for the webhook context -- which learner, which run --
        # then re-raised rather than answered with a hand-built 500. Reaching
        # this means something is broken rather than that the request was bad,
        # so it belongs in the error tracker, and DRF turns it into the 5xx the
        # sender needs in order to retry. A 400 would be worse than either: the
        # sender drops a non-transient 4xx without retrying, losing a grant a
        # second attempt would have mirrored.
        #
        # The role recorded above survives this. ATOMIC_REQUESTS is off, so it
        # is already committed and is not rolled back by the exception.
        raise

    log.info(
        "Webhook: Successfully enrolled user %s in course run %s (mode: %s, role: %s, created: %s)",
        email,
        course_id,
        enrollment.enrollment_mode,
        role,
        created,
    )
    return Response(
        {
            "message": "Enrollment successful",
            "enrollment_id": enrollment.id,
            "active": enrollment.active,
            "edx_enrolled": enrollment.edx_enrolled,
        },
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@extend_schema(exclude=True)
@api_view(["POST"])
@authentication_classes([OAuth2Authentication])
@permission_classes([IsAdminUser])
@versioning_class(NoVersioning)
def edx_certificate_webhook(request):
    """
    Webhook endpoint for receiving certificate creation events from Open edX.

    When Open edX creates a certificate for a user, it sends a POST request
    to this endpoint with the user's email and the course ID. This view then
    fetches the grade from edX, syncs it locally, and creates the corresponding
    certificate in MITx Online.

    Authentication: OAuth2 Bearer token (Django OAuth Toolkit access token).

    Expected payload:
        {
            "email": "learner@example.com",
            "course_id": "course-v1:MITx+1.001x+2025_T1"
        }
    """
    user_email = request.data.get("email")
    course_run_id = request.data.get("course_id")

    log.info(
        "Certificate webhook: Received (email=%s, course_id=%s)",
        user_email,
        course_run_id,
    )

    if not user_email or not course_run_id:
        log.warning(
            "Certificate webhook: missing required fields (email=%s, course_id=%s)",
            user_email,
            course_run_id,
        )
        return Response(
            {"error": "Both 'email' and 'course_id' are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        user = User.objects.get(email__iexact=user_email)
    except User.DoesNotExist:
        log.warning(
            "Certificate webhook: user not found (email=%s, course_id=%s)",
            user_email,
            course_run_id,
        )
        return Response(
            {"error": f"User with email '{user_email}' not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        course_run = CourseRun.objects.get(courseware_id=course_run_id)
    except CourseRun.DoesNotExist:
        log.warning(
            "Certificate webhook: course run not found (email=%s, course_id=%s)",
            user_email,
            course_run_id,
        )
        return Response(
            {"error": f"Course run with id '{course_run_id}' not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    log.info(
        "Certificate webhook: validation passed, processing certificate for user %s, course run %s",
        user_email,
        course_run_id,
    )

    if CourseRunCertificate.objects.filter(user=user, course_run=course_run).exists():
        log.info(
            "Certificate webhook: certificate already exists for user %s and course run %s, skipping",
            user_email,
            course_run_id,
        )
        return Response(status=status.HTTP_200_OK)

    generate_course_run_certificates(
        user=user,
        course_run=course_run,
        force=True,
    )

    log.info(
        "Certificate webhook: finished processing for user %s, course run %s",
        user_email,
        course_run_id,
    )

    return Response(status=status.HTTP_200_OK)


def _upstream_status(exc):
    """
    Map an upstream failure onto our response status.

    A throttle is passed through so the frontend can back off; everything else
    is a bad gateway, because the learner cannot act on it.
    """
    if getattr(exc, "status_code", None) == status.HTTP_429_TOO_MANY_REQUESTS:
        return status.HTTP_429_TOO_MANY_REQUESTS
    return status.HTTP_502_BAD_GATEWAY


NOTIFICATION_PREFERENCES_UNAVAILABLE_DETAIL = (
    "Your course account is still being set up. Please try again shortly."
)


class NotificationPreferencesView(APIView):
    """
    Read and update the learner's own Open edX notification preferences.

    Open edX owns this state — it is what the LMS reads when deciding whether
    to send a learner a notification — so this view proxies straight through
    rather than storing anything locally.
    """

    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAuthenticated,)
    versioning_class = V0Versioning

    @extend_schema(
        operation_id="notification_preferences_retrieve",
        summary="Get the learner's Open edX notification preferences",
        description=(
            "Proxies the learner's preferences from Open edX, which owns this "
            "state. The body is the LMS response verbatim, so its shape follows "
            "the LMS rather than this API."
        ),
        responses={
            200: OpenApiResponse(
                OpenApiTypes.OBJECT,
                description="The LMS response, passed through unchanged.",
            ),
            409: inline_serializer(
                name="NotificationPreferencesUnavailableResponse",
                fields={"detail": serializers.CharField()},
            ),
            502: inline_serializer(
                name="NotificationPreferencesUpstreamErrorResponse",
                fields={"detail": serializers.CharField()},
            ),
        },
    )
    def get(self, request):
        """Return the learner's current notification preferences"""
        try:
            return Response(get_notification_preferences(request.user))
        except NoEdxApiAuthError:
            log.warning(
                "No Open edX auth for %s when reading notification preferences",
                request.user,
            )
            return Response(
                {"detail": NOTIFICATION_PREFERENCES_UNAVAILABLE_DETAIL},
                status=status.HTTP_409_CONFLICT,
            )
        except EdxApiNotificationPreferencesError as exc:
            log.exception("Open edX rejected a notification preferences read")
            return Response(
                {"detail": "Could not load your notification preferences."},
                status=_upstream_status(exc),
            )

    @extend_schema(
        operation_id="notification_preferences_update",
        summary="Change one notification preference",
        description=(
            "Open edX updates a single channel per request, so each toggle or "
            "cadence change is its own call. The body is the LMS response "
            "verbatim."
        ),
        request=NotificationPreferenceUpdateSerializer,
        responses={
            200: OpenApiResponse(
                OpenApiTypes.OBJECT,
                description="The LMS response, passed through unchanged.",
            ),
            409: inline_serializer(
                name="NotificationPreferenceUpdateUnavailableResponse",
                fields={"detail": serializers.CharField()},
            ),
            429: inline_serializer(
                name="NotificationPreferenceUpdateThrottledResponse",
                fields={"detail": serializers.CharField()},
            ),
            502: inline_serializer(
                name="NotificationPreferenceUpdateUpstreamErrorResponse",
                fields={"detail": serializers.CharField()},
            ),
        },
    )
    def put(self, request):
        """Update a single notification preference field"""
        serializer = NotificationPreferenceUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            return Response(
                update_notification_preference(request.user, serializer.validated_data)
            )
        except NoEdxApiAuthError:
            log.warning(
                "No Open edX auth for %s when updating notification preferences",
                request.user,
            )
            return Response(
                {"detail": NOTIFICATION_PREFERENCES_UNAVAILABLE_DETAIL},
                status=status.HTTP_409_CONFLICT,
            )
        except EdxApiNotificationPreferencesError as exc:
            log.exception("Open edX rejected a notification preferences update")
            return Response(
                {
                    "detail": (
                        "Too many changes at once. Please wait a moment and try again."
                        if _upstream_status(exc) == status.HTTP_429_TOO_MANY_REQUESTS
                        else "Could not save your notification preference."
                    )
                },
                status=_upstream_status(exc),
            )
