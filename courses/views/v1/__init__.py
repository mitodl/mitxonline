"""Course views verson 1"""
import logging
from typing import Tuple, Optional, Union

from django.contrib.auth.models import User
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse
from django.conf import settings
from rest_framework import mixins, viewsets, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from courses.api import (
    create_run_enrollments,
    deactivate_run_enrollment,
    get_user_relevant_course_run_qset,
)
from courses.constants import ENROLL_CHANGE_STATUS_UNENROLLED
from courses.models import Course, CourseRun, Program, CourseRunEnrollment
from courses.serializers import (
    CourseRunEnrollmentSerializer,
    CourseRunSerializer,
    CourseSerializer,
    ProgramSerializer,
)
from main import features
from main.constants import (
    USER_MSG_COOKIE_NAME,
    USER_MSG_TYPE_ENROLLED,
    USER_MSG_COOKIE_MAX_AGE,
    USER_MSG_TYPE_ENROLL_FAILED,
    USER_MSG_TYPE_ENROLL_BLOCKED,
)
from main.utils import encode_json_cookie_value
from openedx.api import sync_enrollments_with_edx, unenroll_edx_course_run

log = logging.getLogger(__name__)


class ProgramViewSet(viewsets.ReadOnlyModelViewSet):
    """API view set for Programs"""

    permission_classes = []

    serializer_class = ProgramSerializer
    queryset = Program.objects.filter(live=True)


class CourseViewSet(viewsets.ReadOnlyModelViewSet):
    """API view set for Courses"""

    permission_classes = []

    serializer_class = CourseSerializer
    queryset = Course.objects.filter(live=True)


class CourseRunViewSet(viewsets.ReadOnlyModelViewSet):
    """API view set for CourseRuns"""

    serializer_class = CourseRunSerializer

    def get_queryset(self):
        relevant_to = self.request.query_params.get("relevant_to", None)
        if relevant_to:
            course = Course.objects.filter(readable_id=relevant_to).first()
            if course:
                return get_user_relevant_course_run_qset(course, self.request.user)
            else:
                return CourseRun.objects.none()
        else:
            return CourseRun.objects.all()

    def get_serializer_context(self):
        added_context = {}
        if self.request.query_params.get("relevant_to", None):
            added_context["include_enrolled_flag"] = True
        return {**super().get_serializer_context(), **added_context}


def _validate_enrollment_post_request(
    request: Request,
) -> Union[Tuple[Optional[HttpResponse], None, None], Tuple[None, User, CourseRun]]:
    """
    Validates a request to create an enrollment. Returns a response if validation fails, or a user and course run
    if validation succeeds.
    """
    user = request.user
    run_id_str = request.data.get("run")
    if run_id_str is not None and run_id_str.isdigit():
        run = (
            CourseRun.objects.filter(id=int(run_id_str))
            .select_related("course")
            .first()
        )
    else:
        run = None
    if run is None:
        log.error(
            "Attempting to enroll in a non-existent run (id: %s)", str(run_id_str)
        )
        return HttpResponseRedirect(request.headers["Referer"]), None, None
    if run.course.blocked_countries.filter(country=user.legal_address.country).exists():
        resp = HttpResponseRedirect(request.headers["Referer"])
        resp.set_cookie(
            key=USER_MSG_COOKIE_NAME,
            value=encode_json_cookie_value(
                {
                    "type": USER_MSG_TYPE_ENROLL_BLOCKED,
                }
            ),
            max_age=USER_MSG_COOKIE_MAX_AGE,
        )
        return resp, None, None
    return None, user, run


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_enrollment_view(request):
    """View to handle direct POST requests to enroll in a course run"""
    resp, user, run = _validate_enrollment_post_request(request)
    if resp is not None:
        return resp
    _, edx_request_success = create_run_enrollments(
        user=user,
        runs=[run],
        keep_failed_enrollments=features.is_enabled(features.IGNORE_EDX_FAILURES),
    )
    if edx_request_success or features.is_enabled(features.IGNORE_EDX_FAILURES):
        resp = HttpResponseRedirect(reverse("user-dashboard"))
        cookie_value = {
            "type": USER_MSG_TYPE_ENROLLED,
            "run": run.title,
        }
    else:
        resp = HttpResponseRedirect(request.headers["Referer"])
        cookie_value = {
            "type": USER_MSG_TYPE_ENROLL_FAILED,
        }
    resp.set_cookie(
        key=USER_MSG_COOKIE_NAME,
        value=encode_json_cookie_value(cookie_value),
        max_age=USER_MSG_COOKIE_MAX_AGE,
    )
    return resp


class UserEnrollmentsApiViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """API view set for user enrollments"""

    serializer_class = CourseRunEnrollmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            CourseRunEnrollment.objects.filter(user=self.request.user)
            .select_related("run__course__page")
            .all()
        )

    def get_serializer_context(self):
        if self.action == "list":
            return {"include_page_fields": True}
        else:
            return {"user": self.request.user}

    def list(self, request, *args, **kwargs):
        if features.is_enabled(features.SYNC_ON_DASHBOARD_LOAD):
            try:
                sync_enrollments_with_edx(self.request.user)
            except Exception:  # pylint: disable=broad-except
                log.exception("Failed to sync user enrollments with edX")
        return super().list(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        enrollment = self.get_object()
        deactivated_enrollment = deactivate_run_enrollment(
            enrollment,
            change_status=ENROLL_CHANGE_STATUS_UNENROLLED,
            keep_failed_enrollments=features.is_enabled(features.IGNORE_EDX_FAILURES),
        )
        if deactivated_enrollment is None:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)
