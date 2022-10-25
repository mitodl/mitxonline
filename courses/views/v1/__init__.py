"""Course views verson 1"""
import logging
from typing import Tuple, Optional, Union

from django.contrib.auth.models import User
from django.db import transaction
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse
from requests import ConnectionError as RequestsConnectionError
from requests.exceptions import HTTPError
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
from courses.models import (
    Course,
    CourseRun,
    Program,
    CourseRunEnrollment,
    ProgramEnrollment,
)
from courses.serializers import (
    CourseRunEnrollmentSerializer,
    CourseRunSerializer,
    CourseSerializer,
    ProgramSerializer,
    UserProgramEnrollmentDetailSerializer,
)
from courses.utils import get_program_certificate_by_enrollment
from main import features
from main.constants import (
    USER_MSG_COOKIE_NAME,
    USER_MSG_TYPE_ENROLLED,
    USER_MSG_COOKIE_MAX_AGE,
    USER_MSG_TYPE_ENROLL_FAILED,
    USER_MSG_TYPE_ENROLL_BLOCKED,
)
from main.utils import encode_json_cookie_value
from openedx.api import (
    sync_enrollments_with_edx,
    subscribe_to_edx_course_emails,
    unsubscribe_from_edx_course_emails,
)
from openedx.exceptions import (
    UnknownEdxApiEmailSettingsException,
    EdxApiEmailSettingsErrorException,
    NoEdxApiAuthError,
)

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
    permission_classes = []

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
    if run.course.is_country_blocked(user):
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
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """API view set for user enrollments"""

    serializer_class = CourseRunEnrollmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            CourseRunEnrollment.objects.filter(user=self.request.user)
            .select_related("run__course__page")
            .select_related("run__course__program")
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

    def partial_update(self, request, *args, **kwargs):
        enrollment = self.get_object()
        receive_emails = request.data.get("receive_emails")

        if receive_emails is not None:
            # means if receive_emails is passed in the request body
            with transaction.atomic():
                try:
                    if receive_emails:
                        response = subscribe_to_edx_course_emails(
                            request.user, enrollment.run
                        )
                        enrollment.edx_emails_subscription = True if response else False
                    else:
                        response = unsubscribe_from_edx_course_emails(
                            request.user, enrollment.run
                        )
                        enrollment.edx_emails_subscription = False if response else True
                    enrollment.save()
                    return Response(data=response, status=status.HTTP_200_OK)
                except (
                    EdxApiEmailSettingsErrorException,
                    UnknownEdxApiEmailSettingsException,
                    NoEdxApiAuthError,
                    HTTPError,
                    RequestsConnectionError,
                ) as exc:
                    log.exception(str(exc))
                    return Response(data=str(exc), status=status.HTTP_400_BAD_REQUEST)
        else:
            # only designed to update edx_emails_subscription field
            # TODO: In the future please add the implementation
            # to update the rest of the fields in the PATCH request
            # or separate out the APIs into function-based views.
            raise NotImplementedError


@api_view()
@permission_classes([IsAuthenticated])
def get_user_program_enrollments(request):
    """
    Returns a unified set of program and course enrollments for the current
    user.
    """

    courseruns = (
        CourseRunEnrollment.objects.filter(user=request.user)
        .select_related("run__course__page")
        .select_related("run__course__program")
        .all()
    )

    program_list = {}

    for enrollment in courseruns:
        if enrollment.run.course.program is not None:
            if enrollment.run.course.program.id in program_list:
                program_list[enrollment.run.course.program.id]["enrollments"].append(
                    enrollment
                )
            else:
                program_list[enrollment.run.course.program.id] = {
                    "enrollments": [enrollment],
                    "program": enrollment.run.course.program,
                    "certificate": get_program_certificate_by_enrollment(enrollment),
                }

    non_course_programs = (
        ProgramEnrollment.objects.filter(user=request.user)
        .exclude(program_id__in=program_list.keys())
        .select_related("program")
        .all()
    )

    program_list = list(program_list.values())

    for enrollment in non_course_programs:
        program_list.append(
            {
                "enrollments": [],
                "program": enrollment.program,
                "certificate": get_program_certificate_by_enrollment(enrollment),
            }
        )

    return Response(UserProgramEnrollmentDetailSerializer(program_list, many=True).data)
