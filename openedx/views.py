"""Views for openedx"""

import logging

from django.http import HttpResponse
from drf_spectacular.utils import extend_schema
from oauth2_provider.contrib.rest_framework import OAuth2Authentication
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from courses.api import create_local_enrollment, generate_course_run_certificates
from courses.models import CourseRun, CourseRunCertificate
from openedx.api import (
    get_notification_preferences,
    update_notification_preference,
)
from openedx.constants import EDX_DEFAULT_ENROLLMENT_MODE
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
def edx_enrollment_webhook(request):
    """
    Webhook endpoint that receives enrollment notifications from Open edX.

    When a user needs to be enrolled in a course (e.g., staff/instructor role added,
    or a course team manually enrolls learners from the instructor dashboard), the
    Open edX plugin POSTs to this endpoint so MITx Online can mirror the enrollment
    in the corresponding course run.

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
    mode = request.data.get("mode") or EDX_DEFAULT_ENROLLMENT_MODE

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

    # --- Create local enrollment ---
    try:
        enrollment, created = create_local_enrollment(user, course_run, mode=mode)
    except Exception:
        log.exception(
            "Webhook: Error creating enrollment for user %s in course run %s",
            email,
            course_id,
        )
        return Response(
            {"error": "Failed to create enrollment"},
            status=status.HTTP_400_BAD_REQUEST,
        )

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

    @extend_schema(exclude=True)
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

    @extend_schema(exclude=True)
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
