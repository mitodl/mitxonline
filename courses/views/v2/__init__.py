"""
Course API Views version 2
"""

import contextlib

import django_filters
from django.db.models import Count, Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from mitol.olposthog.features import is_enabled
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import (
    api_view,
    permission_classes,
)
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import (
    AllowAny,
    IsAuthenticated,
    IsAuthenticatedOrReadOnly,
)
from rest_framework.response import Response

from courses.api import create_run_enrollments, deactivate_run_enrollment
from courses.constants import ENROLL_CHANGE_STATUS_UNENROLLED
from courses.models import (
    Course,
    CourseRun,
    CourseRunCertificate,
    CourseRunEnrollment,
    CoursesTopic,
    Department,
    Program,
    ProgramCertificate,
    ProgramCollection,
    ProgramEnrollment,
    ProgramRequirement,
    VerifiableCredential,
)
from courses.serializers.v2.certificates import (
    CourseRunCertificateSerializer,
    ProgramCertificateSerializer,
    VerifiableCredentialSerializer,
)
from courses.serializers.v2.courses import (
    CourseRunEnrollmentSerializer,
    CourseTopicSerializer,
    CourseWithCourseRunsSerializer,
)
from courses.serializers.v2.departments import (
    DepartmentWithCoursesAndProgramsSerializer,
)
from courses.serializers.v2.programs import (
    ProgramCollectionSerializer,
    ProgramSerializer,
    UserProgramEnrollmentDetailSerializer,
)
from courses.utils import (
    get_enrollable_courses,
    get_program_certificate_by_enrollment,
    get_unenrollable_courses,
)
from ecommerce.api import create_verified_program_course_run_enrollment
from main import features
from openapi.utils import extend_schema_get_queryset
from openedx.api import sync_enrollments_with_edx
from openedx.constants import EDX_ENROLLMENT_AUDIT_MODE, EDX_ENROLLMENT_VERIFIED_MODE


class Pagination(PageNumberPagination):
    """Paginator class for infinite loading"""

    page_size = 12
    page_size_query_param = "page_size"
    max_page_size = 100
    ordering = "-created_on"


def user_has_org_access(user, org_id):
    return (
        user
        and user.is_authenticated
        and org_id
        and user.b2b_organizations.filter(id=org_id).exists()
    )


class NumberInFilter(django_filters.BaseInFilter, django_filters.NumberFilter):
    pass


class ProgramFilterSet(django_filters.FilterSet):
    id = NumberInFilter(field_name="id", lookup_expr="in", label="Program ID")
    org_id = django_filters.NumberFilter(method="filter_by_org_id")
    contract_id = django_filters.NumberFilter(method="filter_by_contract_id")

    class Meta:
        model = Program
        fields = ["id", "live", "readable_id", "page__live", "org_id", "contract_id"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def qs(self):
        """If the request isn't explicitly filtering on org_id or contract_id, exclude contracted courses."""

        if "org_id" not in getattr(
            self.request, "GET", {}
        ) and "contract_id" not in getattr(self.request, "GET", {}):
            return super().qs.filter(b2b_only=False)

        return super().qs

    def filter_by_org_id(self, queryset, _, org_id):
        """Filter according to org_id. If the user is in org_id, return only related programs."""
        if self.request and user_has_org_access(self.request.user, org_id):
            return queryset.filter(
                contract_memberships__contract__organization__id=org_id
            )
        else:
            return queryset.filter(b2b_only=False)

    def filter_by_contract_id(self, queryset, _, contract_id):
        """Filter according to contract_id. If the user has access to the contract, return only related programs."""
        user = self.request.user if self.request else None
        if (
            user
            and user.is_authenticated
            and contract_id
            and user.b2b_contracts.filter(id=contract_id).exists()
        ):
            return queryset.filter(contract_memberships__contract__id=contract_id)
        return queryset.filter(b2b_only=False)


class ProgramViewSet(viewsets.ReadOnlyModelViewSet):
    """API viewset for Programs"""

    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class = ProgramSerializer
    pagination_class = Pagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = ProgramFilterSet

    def get_queryset(self):
        return (
            Program.objects.filter()
            .select_related("page", "page__feature_image")
            .prefetch_related(
                Prefetch("departments", queryset=Department.objects.only("id", "name")),
                Prefetch(
                    "all_requirements",
                    queryset=ProgramRequirement.objects.select_related(
                        "course",
                    )
                    .prefetch_related(
                        Prefetch(
                            "course__page__topics",
                            queryset=CoursesTopic.objects.only("name"),
                        )
                    )
                    .only(
                        "id",
                        "path",
                        "depth",
                        "numchild",
                        "node_type",
                        "operator",
                        "operator_value",
                        "program_id",
                        "course_id",
                        "required_program_id",
                        "title",
                        "elective_flag",
                    ),
                ),
                Prefetch(
                    "collection_memberships__collection",
                    queryset=ProgramCollection.objects.only("id", "title"),
                ),
            )
            .order_by("title")
        )

    @extend_schema(
        operation_id="programs_retrieve_v2",
        description="API view set for Programs - v2",
    )
    def retrieve(self, request, *args, **kwargs):
        """Retrieve a specific program."""
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(operation_id="programs_list_v2", description="List Programs - v2")
    def list(self, request, *args, **kwargs):
        """List the available programs."""
        return super().list(request, *args, **kwargs)


class CourseFilterSet(django_filters.FilterSet):
    courserun_is_enrollable = django_filters.BooleanFilter(
        method="filter_courserun_is_enrollable",
        label="Course Run Is Enrollable",
        field_name="courserun_is_enrollable",
    )
    id = NumberInFilter(field_name="id", lookup_expr="in", label="Course ID")
    org_id = django_filters.NumberFilter(
        method="filter_org_id",
        label="Only show courses belonging to this B2B/UAI organization",
        field_name="org_id",
    )
    contract_id = django_filters.NumberFilter(
        method="filter_contract_id",
        label="Only show courses belonging to this B2B contract",
        field_name="contract_id",
    )
    include_approved_financial_aid = django_filters.BooleanFilter(
        method="filter_include_approved_financial_aid",
        label="Include approved financial assistance information",
        field_name="include_approved_financial_aid",
    )

    class Meta:
        model = Course
        fields = [
            "id",
            "live",
            "readable_id",
            "page__live",
            "courserun_is_enrollable",
            "org_id",
            "contract_id",
            "include_approved_financial_aid",
        ]

    def filter_org_id(self, queryset, _, value):
        """
        Filter just courses that have course runs that have B2B courses in them
        that match the specified org_id, if we're in that org.
        """
        user = self.request.user

        if user_has_org_access(user, value):
            return queryset.filter(
                courseruns__b2b_contract__organization_id=value,
                courseruns__b2b_contract__active=True,
            )
        return Course.objects.none()

    def filter_contract_id(self, queryset, _, value):
        """
        Filter courses that have course runs linked to the specified contract_id,
        if the user has access to that contract.
        """
        user = self.request.user

        if (
            user
            and user.is_authenticated
            and value
            and user.b2b_contracts.filter(id=value).exists()
        ):
            return queryset.filter(
                courseruns__b2b_contract__id=value,
                courseruns__b2b_contract__active=True,
            )
        return Course.objects.none()

    def filter_include_approved_financial_aid(self, queryset, *_):
        """
        No-op filter for include_approved_financial_aid.

        This is a serializer context flag, but the filter needs to know about
        the field so the API spec is generated correctly.
        """
        return queryset

    def filter_courserun_is_enrollable(self, queryset, _, value):
        return (
            get_enrollable_courses(queryset)
            if value
            else get_unenrollable_courses(queryset)
        )

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        # perform additional filtering

        filter_keys = self.form.cleaned_data.keys()

        if "courserun_is_enrollable" not in filter_keys:
            queryset = queryset.prefetch_related(
                Prefetch("courseruns", queryset=CourseRun.objects.order_by("id")),
            )

        return queryset


class CourseViewSet(viewsets.ReadOnlyModelViewSet):
    """API view set for Courses"""

    pagination_class = Pagination
    permission_classes = []
    filter_backends = [DjangoFilterBackend]
    serializer_class = CourseWithCourseRunsSerializer
    filterset_class = CourseFilterSet

    def get_queryset(self):
        """Get the queryset for the viewset."""

        return (
            Course.objects.select_related("page")
            .prefetch_related("departments")
            .annotate(count_b2b_courseruns=Count("courseruns__b2b_contract__id"))
            .annotate(count_courseruns=Count("courseruns"))
            .order_by("title")
            .distinct()
        )

    def get_serializer_context(self):
        added_context = {}
        qp = self.request.query_params
        if qp.get("readable_id"):
            added_context["include_programs"] = True
        if qp.get("include_approved_financial_aid"):
            added_context["include_approved_financial_aid"] = True
        if qp.get("org_id") or qp.get("contract_id"):
            # If an org or contract is specified, we extract the user's contracts
            # according to those params, so filtering on some course run data is
            # correct (notably next_run_id).

            added_context["user_contracts"] = []

            user = self.request.user
            if qp.get("org_id"):
                added_context["org_id"] = qp.get("org_id")
                added_context["user_contracts"] = (
                    (
                        user.b2b_contracts.filter(
                            organization__pk=added_context["org_id"]
                        )
                        .values_list("id", flat=True)
                        .all()
                    )
                    if hasattr(user, "b2b_contracts")
                    else []
                )
            if qp.get("contract_id"):
                added_context["contract_id"] = qp.get("contract_id")
                # make sure we filter this - user should be in the contract we're
                # filtering against
                added_context["user_contracts"] = (
                    (
                        user.b2b_contracts.filter(pk=added_context["contract_id"])
                        .values_list("id", flat=True)
                        .all()
                    )
                    if hasattr(user, "b2b_contracts")
                    else []
                )

        return {**super().get_serializer_context(), **added_context}

    @extend_schema(
        operation_id="api_v2_courses_retrieve",
        description="Retrieve a specific course - API v2",
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        operation_id="api_v2_courses_list", description="List all courses - API v2"
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class DepartmentViewSet(viewsets.ReadOnlyModelViewSet):
    """API view set for Departments"""

    serializer_class = DepartmentWithCoursesAndProgramsSerializer
    permission_classes = []

    def get_queryset(self):
        return Department.objects.for_serialization().order_by("name")

    @extend_schema(
        operation_id="departments_retrieve_v2",
        description="Get department details - v2",
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        operation_id="departments_list_v2", description="List departments - v2"
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class CourseTopicViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Readonly viewset for parent course topics.
    """

    permission_classes = []
    serializer_class = CourseTopicSerializer

    def get_queryset(self):
        """
        Returns parent topics with course count > 0.
        """
        return CoursesTopic.parent_topics_with_courses()


class ProgramCollectionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Readonly viewset for ProgramCollection objects.
    """

    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class = ProgramCollectionSerializer
    pagination_class = Pagination

    def get_queryset(self):
        """
        Returns all ProgramCollection objects ordered by title.
        Prefetches collection_items and related programs for efficient serialization.
        """
        return (
            ProgramCollection.objects.select_related()
            .prefetch_related(
                "collection_items__program", "collection_items__program__departments"
            )
            .order_by("title")
        )


class UserEnrollmentFilterSet(django_filters.FilterSet):
    """Filter set for user enrollments with B2B organization filtering."""

    org_id = django_filters.NumberFilter(
        method="filter_org_id",
        label="Filter by B2B organization ID",
    )
    exclude_b2b = django_filters.BooleanFilter(
        method="filter_exclude_b2b",
        label="Exclude B2B enrollments (enrollments linked to course runs with B2B contracts)",
    )

    class Meta:
        model = CourseRunEnrollment
        fields = ["org_id", "exclude_b2b"]

    def filter_exclude_b2b(self, queryset, name, value):  # noqa: ARG002
        """Filter out B2B enrollments if exclude_b2b is True."""
        if value:
            return queryset.filter(run__b2b_contract__isnull=True)
        return queryset

    def filter_org_id(self, queryset, name, value):  # noqa: ARG002
        """Filter enrollments by B2B organization ID."""
        if value:
            return queryset.filter(run__b2b_contract__organization_id=value)
        return queryset


class UserEnrollmentsApiViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """API view set for user enrollments - v2"""

    serializer_class = CourseRunEnrollmentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_class = UserEnrollmentFilterSet

    @extend_schema_get_queryset(CourseRunEnrollment.objects.none())
    def get_queryset(self):
        """Get the queryset for user enrollments."""
        return (
            CourseRunEnrollment.objects.filter(user=self.request.user)
            .select_related(
                "run__course__page",
                "user",
                "run",
                "run__b2b_contract",
                "run__b2b_contract__organization",
            )
            .all()
        )

    def get_serializer_context(self):
        """Get the serializer context."""
        if self.action == "list":
            return {"include_page_fields": True}
        else:
            return {"user": self.request.user}

    @extend_schema(
        operation_id="user_enrollments_list_v2",
        description="List user enrollments with B2B organization and contract information - API v2. "
        "Use ?exclude_b2b=true to filter out enrollments linked to course runs with B2B contracts. "
        "Use ?org_id=<id> to filter enrollments by specific B2B organization.",
    )
    def list(self, request, *args, **kwargs):
        """List user enrollments with optional sync."""
        if is_enabled(features.SYNC_ON_DASHBOARD_LOAD):
            with contextlib.suppress(Exception):
                sync_enrollments_with_edx(self.request.user)
        return super().list(request, *args, **kwargs)

    @extend_schema(
        operation_id="user_enrollments_create_v2",
        description="Create a new user enrollment - API v2",
    )
    def create(self, request, *args, **kwargs):
        """Create a new enrollment."""
        return super().create(request, *args, **kwargs)

    @extend_schema(
        operation_id="user_enrollments_destroy_v2",
        description="Unenroll from a course - API v2",
    )
    def destroy(self, request, *args, **kwargs):  # noqa: ARG002
        """Unenroll from a course."""
        enrollment = self.get_object()
        deactivated_enrollment = deactivate_run_enrollment(
            enrollment,
            change_status=ENROLL_CHANGE_STATUS_UNENROLLED,
            keep_failed_enrollments=is_enabled(features.IGNORE_EDX_FAILURES),
        )
        if deactivated_enrollment is None:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    parameters=[
        OpenApiParameter(
            "program_id",
            str,
            OpenApiParameter.PATH,
            description="Readable ID for the program.",
        ),
        OpenApiParameter(
            "courserun_id",
            str,
            OpenApiParameter.PATH,
            description="Readable ID for the course run to enroll in.",
        ),
    ],
    request=None,
    responses={
        status.HTTP_201_CREATED: CourseRunEnrollmentSerializer,
        status.HTTP_204_NO_CONTENT: None,
        status.HTTP_404_NOT_FOUND: None,
    },
)
@api_view(
    http_method_names=["post"],
)
@permission_classes(
    [
        IsAuthenticated,
    ]
)
def add_verified_program_course_enrollment(request, program_id: str, courserun_id: str):
    """
    Create a program-related course enrollment for the learner.

    Some special handling is needed for program-related course run enrollments
    when the learner has an enrollment in the program. The learner should get a
    course run enrollment that matches their program enrollment at no additional
    charge. However, if the learner is enrolling in a course that's an elective,
    and they have already enrolled in enough electives to satisfy the program's
    requirements, they should then get an audit enrollment. (This won't preclude
    them from getting a certificate for the course itself but they'll have to buy
    the upgrade separately.)
    """

    try:
        program_enrollment = ProgramEnrollment.objects.filter(
            program__readable_id=program_id, user=request.user
        ).get()
    except ProgramEnrollment.DoesNotExist:
        # Learner isn't in the program so abort.
        return Response(status=status.HTTP_404_NOT_FOUND)

    if CourseRunEnrollment.objects.filter(
        run__courseware_id=courserun_id,
        user=request.user,
        enrollment_mode=program_enrollment.enrollment_mode,
    ).exists():
        # Learner already has a matching enrollment, so nothing to do.
        return Response(status=status.HTTP_204_NO_CONTENT)

    run = CourseRun.objects.filter(courseware_id=courserun_id).get()

    if program_enrollment.enrollment_mode == EDX_ENROLLMENT_AUDIT_MODE:
        # Audit enrollments just get created, regardless of whether or not
        # the course is an elective.
        enrollments, _ = create_run_enrollments(
            request.user,
            [run],
            mode=EDX_ENROLLMENT_AUDIT_MODE,
            keep_failed_enrollments=True,
        )
        return Response(
            CourseRunEnrollmentSerializer(enrollments[0]).data,
            status=status.HTTP_201_CREATED,
        )

    if run not in program_enrollment.program.required_courses and (
        CourseRunEnrollment.objects.filter(
            run__course__in=program_enrollment.program.elective_courses,
            user=request.user,
            active=True,
            enrollment_mode=EDX_ENROLLMENT_VERIFIED_MODE,
        ).count()
        >= (program_enrollment.program.minimum_elective_courses_requirement or 1)
    ):
        # Too many verified elective enrollments, so make this as an audit one.
        enrollments, _ = create_run_enrollments(
            request.user,
            [run],
            mode=EDX_ENROLLMENT_AUDIT_MODE,
            keep_failed_enrollments=True,
        )
        return Response(
            CourseRunEnrollmentSerializer(enrollments[0]).data,
            status=status.HTTP_201_CREATED,
        )

    # Everything checks out for a verified enrollment, so generate one.
    # This requires generating an order.

    enrollment = create_verified_program_course_run_enrollment(
        request, run, program_enrollment.program
    )

    return Response(
        CourseRunEnrollmentSerializer(enrollment).data,
        status=status.HTTP_201_CREATED,
    )


@extend_schema(
    parameters=[
        OpenApiParameter("cert_uuid", OpenApiTypes.UUID, OpenApiParameter.PATH),
    ],
    responses=CourseRunCertificateSerializer,
)
@api_view(["GET"])
@permission_classes([AllowAny])
def get_course_certificate(request, cert_uuid):
    """Get a course certificate by UUID."""

    cert_uuid = serializers.UUIDField().to_internal_value(cert_uuid)

    cert = get_object_or_404(CourseRunCertificate, is_revoked=False, uuid=cert_uuid)

    return Response(
        CourseRunCertificateSerializer(cert, context={"request": request}).data
    )


@extend_schema(
    parameters=[
        OpenApiParameter("cert_uuid", OpenApiTypes.UUID, OpenApiParameter.PATH),
    ],
    responses=ProgramCertificateSerializer,
)
@api_view(["GET"])
@permission_classes([AllowAny])
def get_program_certificate(request, cert_uuid):
    """Get a program certificate by UUID."""

    cert_uuid = serializers.UUIDField().to_internal_value(cert_uuid)

    cert = get_object_or_404(ProgramCertificate, is_revoked=False, uuid=cert_uuid)

    return Response(
        ProgramCertificateSerializer(cert, context={"request": request}).data
    )


class UserProgramEnrollmentsViewSet(viewsets.ViewSet):
    """ViewSet for user program enrollments with v2 serializers."""

    permission_classes = [IsAuthenticated]

    id_parameter = OpenApiParameter(
        name="id",
        type=OpenApiTypes.INT,
        location=OpenApiParameter.PATH,
        description="Program enrollment ID",
        required=True,
    )

    @extend_schema(
        operation_id="v2_program_enrollments_list",
        responses={200: UserProgramEnrollmentDetailSerializer(many=True)},
        parameters=[],
    )
    def list(self, request):
        """
        Returns a unified set of program and course enrollments for the current
        user using v2 serializers.
        """
        program_enrollments = (
            ProgramEnrollment.objects.select_related(
                "program",
                "program__page",
            )
            .filter(user=request.user)
            .filter(~Q(change_status=ENROLL_CHANGE_STATUS_UNENROLLED))
            .order_by("-id")
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
                    .select_related("run__course__page", "run__b2b_contract")
                    .order_by("-id"),
                    "program": enrollment.program,
                    "certificate": get_program_certificate_by_enrollment(enrollment),
                }
            )

        return Response(
            UserProgramEnrollmentDetailSerializer(program_list, many=True).data
        )

    @extend_schema(
        operation_id="v2_program_enrollments_retrieve",
        responses={200: UserProgramEnrollmentDetailSerializer},
        parameters=[id_parameter],
    )
    def retrieve(self, request, pk=None):
        """
        Retrieve a specific program enrollment using v2 serializers.
        """
        program = Program.objects.get(pk=pk)
        enrollment = ProgramEnrollment.objects.get(user=request.user, program=program)
        serializer = UserProgramEnrollmentDetailSerializer(
            enrollment, context={"request": request}
        )
        return Response(serializer.data)

    @extend_schema(
        operation_id="v2_program_enrollments_destroy",
        responses={200: UserProgramEnrollmentDetailSerializer(many=True)},
        parameters=[id_parameter],
    )
    def destroy(self, request, pk=None):
        """
        Unenroll the user from this program. This is simpler than the corresponding
        function for CourseRunEnrollments; edX doesn't really know what programs
        are so there's nothing to process there.
        """

        program = Program.objects.get(pk=pk)
        ProgramEnrollment.objects.update_or_create(
            user=request.user,
            program=program,
            defaults={"change_status": ENROLL_CHANGE_STATUS_UNENROLLED},
        )

        return self.list(request)


@extend_schema(
    description="Returns the json for the verifiable credential with the given ID",
    responses={200: VerifiableCredentialSerializer(many=True)},
)
@api_view(["GET"])
@permission_classes([AllowAny])
def download_course_credential(request, credential_id):  # noqa: ARG001
    credential = get_object_or_404(
        VerifiableCredential,
        pk=credential_id,
    )
    response = JsonResponse(credential.credential_data)
    response["Content-Disposition"] = (
        f'attachment; filename="credential_{credential_id}.json"'
    )
    return response


@extend_schema(
    description="Returns the json for the verifiable credential with the given ID",
    responses={200: VerifiableCredentialSerializer(many=True)},
)
@api_view(["GET"])
@permission_classes([AllowAny])
def download_program_credential(request, credential_id):  # noqa: ARG001
    credential = get_object_or_404(
        VerifiableCredential,
        pk=credential_id,
    )
    response = JsonResponse(credential.credential_data)
    response["Content-Disposition"] = (
        f'attachment; filename="credential_{credential_id}.json"'
    )
    return response
