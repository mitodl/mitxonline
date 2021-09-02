"""Course views verson 1"""
import logging

from django.http import HttpResponseRedirect
from django.urls import reverse
from rest_framework import mixins, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from courses.api import create_run_enrollments
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
)
from main.utils import encode_json_cookie_value

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
    queryset = CourseRun.objects.all()


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_enrollment_view(request):
    """View to handle direct POST requests to enroll in a course run"""
    user = request.user
    run_id_str = request.data.get("run")
    if run_id_str is not None and run_id_str.isdigit():
        run = CourseRun.objects.filter(id=int(run_id_str)).first()
    else:
        run = None
    if run is None:
        log.error(
            "Attempting to enroll in a non-existent run (id: %s)", str(run_id_str)
        )
        return HttpResponseRedirect(request.get_raw_uri())
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
    mixins.CreateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet
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
