"""Views for openedx"""

import logging

from django.http import HttpResponse
from drf_spectacular.utils import extend_schema
from oauth2_provider.contrib.rest_framework import OAuth2Authentication
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from courses.api import create_local_enrollment, generate_course_run_certificates
from courses.models import CourseRun, CourseRunCertificate
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

    When a user needs to be enrolled in a course (e.g., staff/instructor role added),
    the Open edX plugin POSTs to this endpoint so MITx Online can enroll them as an
    auditor in the corresponding course run.

    Authentication: OAuth2 Bearer token (Django OAuth Toolkit access token).

    Expected payload:
        {
            "email": "instructor@example.com",
            "course_id": "course-v1:MITx+1.001x+2025_T1",
            "role": "instructor"
        }
    """
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
        enrollment, created = create_local_enrollment(user, course_run)
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
        "Webhook: Successfully enrolled user %s in course run %s as auditor (role: %s, created: %s)",
        email,
        course_id,
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
class ProcessCertificateWebhookView(APIView):
    """
    API view for receiving certificate creation events from Open edX.

    When Open edX creates a certificate for a user, it sends a POST request
    to this endpoint with the user's email and the course ID. This view then
    fetches the grade from edX, syncs it locally, and creates the corresponding
    certificate in MITx Online.
    """

    authentication_classes = [OAuth2Authentication]
    permission_classes = [IsAdminUser]

    def post(self, request):
        user_email = request.data.get("user_id")
        course_run_id = request.data.get("course_id")

        if not user_email or not course_run_id:
            return Response(
                {"error": "Both 'user_id' and 'course_id' are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(email__iexact=user_email)
        except User.DoesNotExist:
            return Response(
                {"error": f"User with email '{user_email}' not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            course_run = CourseRun.objects.get(courseware_id=course_run_id)
        except CourseRun.DoesNotExist:
            return Response(
                {"error": f"Course run with id '{course_run_id}' not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        log.info(
            "Certificate webhook received for user %s, course run %s",
            user_email,
            course_run_id,
        )

        if CourseRunCertificate.objects.filter(
            user=user, course_run=course_run
        ).exists():
            log.info(
                "Certificate already exists for user %s and course run %s, skipping",
                user_email,
                course_run_id,
            )
            return Response(status=status.HTTP_200_OK)

        generate_course_run_certificates(
            user=user,
            course_run=course_run,
            force=True,
        )

        return Response(status=status.HTTP_200_OK)
