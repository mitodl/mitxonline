"""Views for openedx"""

import logging

from django.conf import settings
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from courses.api import create_run_enrollments
from courses.models import CourseRun
from users.models import User

log = logging.getLogger(__name__)


def openedx_private_auth_complete(request):  # noqa: ARG001
    """Responds with a simple HTTP_200_OK"""
    # NOTE: this is only meant as a landing endpoint for api.create_edx_auth_token() flow
    return HttpResponse(status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([AllowAny])
def edx_course_staff_webhook(request):  # noqa: PLR0911
    """
    Webhook endpoint that receives course staff addition notifications from Open edX.

    When an instructor or staff member is added to a course in Open edX, the
    ol_openedx_course_staff_webhook plugin POSTs to this endpoint so MITx Online
    can enroll them as an auditor in the corresponding course run.

    Expected payload:
        {
            "email": "instructor@example.com",
            "course_id": "course-v1:MITx+1.001x+2025_T1",
            "role": "instructor"
        }
    """
    # --- Authenticate via Bearer token ---
    webhook_key = getattr(settings, "OPENEDX_WEBHOOK_KEY", None)
    if not webhook_key:
        log.error("OPENEDX_WEBHOOK_KEY is not configured")
        return Response(
            {"error": "Webhook is not configured"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    auth_header = request.META.get("HTTP_AUTHORIZATION", "")
    if not auth_header.startswith("Bearer "):
        return Response(
            {"error": "Missing or invalid Authorization header"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    token = auth_header[len("Bearer ") :]
    if token != webhook_key:
        return Response(
            {"error": "Invalid webhook token"},
            status=status.HTTP_403_FORBIDDEN,
        )

    # --- Validate payload ---
    email = request.data.get("email")
    course_id = request.data.get("course_id")
    role = request.data.get("role", "")

    if not email or not course_id:
        return Response(
            {"error": "Missing required fields: email and course_id"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # --- Look up user ---
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        log.warning(
            "Webhook: No user found with email %s for course %s (role: %s)",
            email,
            course_id,
            role,
        )
        return Response(
            {"error": f"User with email {email} not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except User.MultipleObjectsReturned:
        log.warning(
            "Webhook: Multiple users found with email %s for course %s (role: %s)",
            email,
            course_id,
            role,
        )
        return Response(
            {"error": f"Multiple users found with email {email}"},
            status=status.HTTP_409_CONFLICT,
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

    # --- Enroll user as auditor ---
    try:
        enrollments, _edx_request_success = create_run_enrollments(
            user,
            [course_run],
            keep_failed_enrollments=True,
        )
    except Exception:
        log.exception(
            "Webhook: Error creating enrollment for user %s in course run %s",
            email,
            course_id,
        )
        return Response(
            {"error": "Failed to create enrollment"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if enrollments:
        enrollment = enrollments[0]
        log.info(
            "Webhook: Successfully enrolled user %s in course run %s as auditor (role: %s, active: %s)",
            email,
            course_id,
            role,
            enrollment.active,
        )
        return Response(
            {
                "message": "Enrollment successful",
                "enrollment_id": enrollment.id,
                "active": enrollment.active,
            },
            status=status.HTTP_200_OK,
        )
    else:
        log.error(
            "Webhook: Enrollment creation returned empty for user %s in course run %s",
            email,
            course_id,
        )
        return Response(
            {"error": "Enrollment creation failed"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
