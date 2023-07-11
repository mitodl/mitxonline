"""Course views verson 1"""
import logging
from typing import Optional, Tuple, Union

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from requests import ConnectionError as RequestsConnectionError
from requests.exceptions import HTTPError
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from reversion.models import Version

from courses.api import (
    create_run_enrollments,
    deactivate_run_enrollment,
    get_user_relevant_course_run_qset,
)
from courses.constants import ENROLL_CHANGE_STATUS_UNENROLLED
from courses.models import (
    Course,
    CourseRun,
    CourseRunEnrollment,
    LearnerProgramRecordShare,
    PartnerSchool,
    Program,
    ProgramEnrollment,
    ProgramRequirement,
    ProgramRequirementNodeType,
)
from courses.serializers import (
    CourseRunEnrollmentSerializer,
    CourseRunSerializer,
    CourseSerializer,
    LearnerRecordSerializer,
    PartnerSchoolSerializer,
    ProgramSerializer,
    UserProgramEnrollmentDetailSerializer,
)
from courses.tasks import send_partner_school_email
from courses.utils import get_program_certificate_by_enrollment
from ecommerce.models import FulfilledOrder, Order, PendingOrder, Product
from hubspot_sync.task_helpers import sync_hubspot_deal
from main import features
from main.constants import (
    USER_MSG_COOKIE_MAX_AGE,
    USER_MSG_COOKIE_NAME,
    USER_MSG_TYPE_ENROLL_BLOCKED,
    USER_MSG_TYPE_ENROLL_FAILED,
    USER_MSG_TYPE_ENROLLED,
)
from main.utils import encode_json_cookie_value
from openedx.api import (
    subscribe_to_edx_course_emails,
    sync_enrollments_with_edx,
    unsubscribe_from_edx_course_emails,
)
from openedx.exceptions import (
    EdxApiEmailSettingsErrorException,
    NoEdxApiAuthError,
    UnknownEdxApiEmailSettingsException,
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
    if run_id_str is not None and str(run_id_str).isdigit():
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

    def respond(data, status=True):
        """
        Either return a redirect or Ok/Fail based on status.
        """

        if "isapi" in request.data:
            return Response("Ok" if status else "Fail")

        return HttpResponseRedirect(data)

    if edx_request_success or features.is_enabled(features.IGNORE_EDX_FAILURES):
        resp = respond(reverse("user-dashboard"))
        cookie_value = {
            "type": USER_MSG_TYPE_ENROLLED,
            "run": run.title,
        }

        # Check for an existing fulfilled order prior, otherwise get or create a PendingOrder.
        # This can occur if the user has a verified enrollment that is not synced with Edx,
        # and then attempts to enroll in the course again.
        product = Product.objects.filter(
            object_id=run.id,
            content_type=ContentType.objects.get_for_model(CourseRun),
        ).first()
        if product is None:
            log.exception("No product found for that course with courseware_id %s", run)
        else:
            product_version = Version.objects.get_for_object(product).first()
            product_object_id = product.object_id
            product_content_type = product.content_type_id
            order = FulfilledOrder.objects.filter(
                state=Order.STATE.FULFILLED,
                purchaser=user,
                lines__purchased_object_id=product_object_id,
                lines__purchased_content_type_id=product_content_type,
                lines__product_version=product_version,
            )
            if not order:
                # Create PendingOrder
                order = PendingOrder.create_from_product(product, user)
                sync_hubspot_deal(order)
            else:
                sync_hubspot_deal(order.first())
    else:
        resp = respond(request.headers["Referer"])
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


class UserProgramEnrollmentsViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        """
        Returns a unified set of program and course enrollments for the current
        user.
        """

        program_enrollments = (
            ProgramEnrollment.objects.select_related(
                "program",
                "program__page",
            )
            .filter(user=request.user)
            .filter(~Q(change_status=ENROLL_CHANGE_STATUS_UNENROLLED))
            .all()
        )

        program_list = []

        for enrollment in program_enrollments:
            courses = [course[0] for course in enrollment.program.courses]

            program_list.append(
                {
                    "enrollments": CourseRunEnrollment.objects.filter(
                        user=request.user, run__course__in=courses
                    )
                    .filter(~Q(change_status=ENROLL_CHANGE_STATUS_UNENROLLED))
                    .select_related("run__course__page")
                    .all(),
                    "program": enrollment.program,
                    "certificate": get_program_certificate_by_enrollment(enrollment),
                }
            )

        return Response(
            UserProgramEnrollmentDetailSerializer(program_list, many=True).data
        )

    def destroy(self, request, pk=None):
        """
        Unenroll the user from this program. This is simpler than the corresponding
        function for CourseRunEnrollments; edX doesn't really know what programs
        are so there's nothing to process there.
        """

        program = Program.objects.get(pk=pk)
        (enrollment, created) = ProgramEnrollment.objects.update_or_create(
            user=request.user,
            program=program,
            defaults={"change_status": ENROLL_CHANGE_STATUS_UNENROLLED},
        )

        return self.list(request)


class PartnerSchoolViewSet(viewsets.ReadOnlyModelViewSet):
    """API view set for PartnerSchools"""

    permission_classes = [
        IsAuthenticated,
    ]

    serializer_class = PartnerSchoolSerializer
    queryset = PartnerSchool.objects.all()


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_learner_record(request, pk):
    program = Program.objects.get(pk=pk)

    return Response(LearnerRecordSerializer(program, context={"request": request}).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def get_learner_record_share(request, pk):
    """
    Sets up a sharing link for the learner's record. Returns back the entire
    learner record.
    """
    program = Program.objects.get(pk=pk)

    school = None

    if "partnerSchool" in request.data and request.data["partnerSchool"] is not None:
        # OK here to just turn on the existing partner school share if there's
        # already one - these technically don't get revoked.
        try:
            school = PartnerSchool.objects.get(pk=request.data["partnerSchool"])
        except:
            return Response("Partner school not found.", status.HTTP_404_NOT_FOUND)

        (ps_share, created) = LearnerProgramRecordShare.objects.filter(
            user=request.user, program=program, partner_school=school
        ).get_or_create(user=request.user, program=program, partner_school=school)
        ps_share.is_active = True
        ps_share.save()

        # Send email
        send_partner_school_email.delay(ps_share.share_uuid)
    else:
        # If we're creating an anonymous one, we need to check to make sure the
        # existing link hasn't been deactivated (if there is one). We don't
        # want to re-activate an existing one so people can revoke the links
        # that are out there and get new ones. But, if there's a still active
        # record out there, we don't want to make another new one either.

        (ps_share, created) = LearnerProgramRecordShare.objects.filter(
            user=request.user, program=program, partner_school=None, is_active=True
        ).get_or_create(
            user=request.user, program=program, partner_school=None, is_active=True
        )

    return Response(LearnerRecordSerializer(program, context={"request": request}).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def revoke_learner_record_share(request, pk):
    """
    Disables sharing links for the learner's record. This only applies to the
    anonymous ones; shares sent to partner schools are always allowed once they
    are sent.
    """
    program = Program.objects.get(pk=pk)

    LearnerProgramRecordShare.objects.filter(
        user=request.user, partner_school=None, program=program
    ).update(is_active=False)

    return Response(LearnerRecordSerializer(program, context={"request": request}).data)


@api_view(["GET"])
@permission_classes([])
def get_learner_record_from_uuid(request, uuid):
    """
    Does mostly the same thing as get_learner_record, but sets context to skip
    the partner school and sharing information.
    """
    record = LearnerProgramRecordShare.objects.filter(
        is_active=True, share_uuid=uuid
    ).first()

    if record is None:
        return Response([], status=status.HTTP_404_NOT_FOUND)

    return Response(
        LearnerRecordSerializer(
            record.program, context={"user": record.user, "anonymous_pull": True}
        ).data
    )
