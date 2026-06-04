"""
Course API Views version 3
"""

import logging
import re

import django_filters
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import (
    AllowAny,
    BasePermission,
    IsAuthenticated,
)
from rest_framework.response import Response

from b2b.models import ContractPage
from courses.api import create_program_enrollments, deactivate_run_enrollment
from courses.constants import COURSE_KEY_PATTERN, ENROLL_CHANGE_STATUS_UNENROLLED
from courses.models import (
    Course,
    CourseRun,
    CourseRunEnrollment,
    Program,
    ProgramEnrollment,
)
from courses.serializers.v3.courses import (
    CourseOutlineResponseSerializer,
    CourseRunEnrollmentSerializer,
    CourseVariantRunsResponseSerializer,
    IngestibleCourseWithCourseRunsSerializer,
)
from courses.serializers.v3.programs import (
    ProgramEnrollmentCreateSerializer,
    ProgramEnrollmentSerializer,
)
from courses.utils import get_enrollable_courseruns_qs
from courses.views.utils import Pagination
from ecommerce.models import Product
from main import features
from openedx.api import get_edx_course_outline
from openedx.constants import EDX_ENROLLMENT_VERIFIED_MODE
from openedx.exceptions import EdxApiCourseOutlineError

log = logging.getLogger(__name__)


class IsEtlUser(BasePermission):
    """Allow only is_etl flagged users through."""

    message = "Invalid user."

    def has_permission(self, request, view):  # noqa: ARG002
        """Check the user's is_etl flag."""

        return (
            request.user
            and not request.user.is_anonymous
            and (request.user.is_etl or request.user.is_superuser)
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


@extend_schema_view(
    list=extend_schema(
        operation_id="user_enrollments_list_v3",
        description="List user enrollments with B2B organization and contract information - API v3. "
        "Use ?exclude_b2b=true to filter out enrollments linked to course runs with B2B contracts. "
        "Use ?org_id=<id> to filter enrollments by specific B2B organization.",
    ),
    create=extend_schema(
        operation_id="user_enrollments_create_v3",
        description="Create a new user enrollment - API v3",
    ),
)
class UserEnrollmentsApiViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """API view set for user enrollments - v3"""

    serializer_class = CourseRunEnrollmentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_class = UserEnrollmentFilterSet

    queryset = (
        CourseRunEnrollment.objects.select_related(
            # these possibly get joined anyway via filer, so select over prefetch
            "run",
            "run__b2b_contract",
        )
        .prefetch_related(
            "run__course",
            "run__course__page",
            Prefetch(
                "run__enrollment_modes",
                to_attr="prefetched_enrollment_modes",
            ),
            Prefetch(
                "run__products",
                queryset=Product.objects.only("id", "price", "is_active"),
                to_attr="prefetched_products",
            ),
        )
        .prefetch("certificate", "grades")
        .order_by("id")
    )

    def get_queryset(self):
        """Get the queryset for user enrollments."""
        return super().get_queryset().filter(user=self.request.user)

    def get_serializer_context(self):
        """Get the serializer context."""
        return {"user": self.request.user}

    @extend_schema(
        operation_id="user_enrollments_destroy_v3",
        description="Unenroll from a course - API v3",
    )
    def destroy(self, request, *args, **kwargs):  # noqa: ARG002
        """Unenroll from a course."""
        enrollment = self.get_object()
        deactivated_enrollment = deactivate_run_enrollment(
            enrollment,
            change_status=ENROLL_CHANGE_STATUS_UNENROLLED,
            keep_failed_enrollments=settings.FEATURES.get(
                features.IGNORE_EDX_FAILURES, False
            ),
        )
        if deactivated_enrollment is None:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema_view(
    list=extend_schema(operation_id="v3_program_enrollments_list"),
    retrieve=extend_schema(operation_id="v3_program_enrollments_retrieve"),
    create=extend_schema(operation_id="v3_program_enrollments_create"),
    destroy=extend_schema(
        operation_id="v3_program_enrollments_destroy",
        parameters=[
            OpenApiParameter(
                name="program_id",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description="Program ID",
                required=True,
            )
        ],
        responses={204: None},
    ),
)
class UserProgramEnrollmentsViewSet(
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """ViewSet for user program enrollments with v3 serializers."""

    permission_classes = [IsAuthenticated]

    serializer_class = ProgramEnrollmentSerializer

    lookup_field = "program_id"

    queryset = (
        ProgramEnrollment.objects.prefetch_related(
            "program",
        )
        .filter(~Q(change_status=ENROLL_CHANGE_STATUS_UNENROLLED))
        .prefetch("certificate")
        .order_by("-id")
    )

    def get_queryset(self):
        """Get the queryset for the current user"""
        request = self.request
        return super().get_queryset().filter(user=request.user)

    def get_serializer_class(self):
        """Return appropriate serializer class based on action."""
        if self.action == "create":
            return ProgramEnrollmentCreateSerializer
        return ProgramEnrollmentSerializer

    def create(self, request, *args, **kwargs):  # noqa: ARG002
        """
        Create a program enrollment for the authenticated user.

        Returns 200 if the user already has an active enrollment,
        201 if a new enrollment was created or an inactive one was reactivated.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        program = serializer.program

        # Check if the user already has an active enrollment for this program
        existing_enrollment = (
            self.get_queryset()
            .filter(
                program=program,
            )
            .first()
        )

        if existing_enrollment:
            response_serializer = ProgramEnrollmentSerializer(existing_enrollment)
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        # Create the enrollment using default enrollment mode (audit)
        enrollments = create_program_enrollments(request.user, [program])
        if not enrollments:
            raise ValueError("Failed to create program enrollment.")  # noqa: EM101
        response_serializer = ProgramEnrollmentSerializer(enrollments[0])
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):  # noqa: ARG002
        """
        Unenroll the user from this program.

        Returns 204 No Content. Idempotent - returns 204 even if not currently
        enrolled. Returns 404 if the program does not exist.
        """
        program_id = kwargs.get(self.lookup_field)
        get_object_or_404(Program, pk=program_id)

        enrollment = self.get_queryset().filter(program_id=program_id).first()
        if enrollment:
            if not enrollment.can_unenroll:
                return Response(
                    {
                        "message": "Cannot unenroll from a purchased program, contact support."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            enrollment.deactivate_and_save(ENROLL_CHANGE_STATUS_UNENROLLED)

        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    operation_id="course_outline_retrieve_v3",
    description="Fetch course outline data for the given course key from Open edX.",
    parameters=[
        OpenApiParameter(
            name="course_id",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.PATH,
            required=True,
            description="Open edX course key (URL-encoded recommended), e.g. course-v1%3AOpenedX%2BDemoX%2BDemoCourse",
        )
    ],
    responses={
        200: CourseOutlineResponseSerializer,
        400: inline_serializer(
            name="CourseOutlineBadRequestResponse",
            fields={"detail": serializers.CharField()},
        ),
        502: inline_serializer(
            name="CourseOutlineUpstreamErrorResponse",
            fields={"detail": serializers.CharField()},
        ),
        500: inline_serializer(
            name="CourseOutlineServerErrorResponse",
            fields={"detail": serializers.CharField()},
        ),
    },
    examples=[
        OpenApiExample(
            "CourseOutlineSuccess",
            value={
                "course_id": "course-v1:OpenedX+DemoX+DemoCourse",
                "generated_at": "2026-04-10T07:17:20Z",
                "modules": [
                    {
                        "id": "block-v1:OpenedX+DemoX+DemoCourse+type@chapter+block@abc123",
                        "title": "Module 1",
                        "effort_time": 0,
                        "effort_activities": 0,
                        "counts": {
                            "videos": 2,
                            "readings": 1,
                            "problems": 1,
                            "assignments": 0,
                            "app_items": 0,
                        },
                    }
                ],
            },
            response_only=True,
            status_codes=["200"],
        ),
        OpenApiExample(
            "InvalidCourseId",
            value={
                "detail": "Invalid course_id format. Expected an Open edX course key."
            },
            response_only=True,
            status_codes=["400"],
        ),
        OpenApiExample(
            "UpstreamError",
            value={"detail": "Unable to fetch course outline from Open edX."},
            response_only=True,
            status_codes=["502"],
        ),
    ],
)
@api_view(["GET"])
@permission_classes([AllowAny])
def get_course_outline(request, course_id):  # noqa: ARG001
    """
    Return course outline data from Open edX for the specified course key.
    """
    if not re.fullmatch(COURSE_KEY_PATTERN, course_id):
        return Response(
            {"detail": "Invalid course_id format. Expected an Open edX course key."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        outline_data = get_edx_course_outline(course_id)
    except EdxApiCourseOutlineError:
        return Response(
            {"detail": "Unable to fetch course outline from Open edX."},
            status=status.HTTP_502_BAD_GATEWAY,
        )
    except ImproperlyConfigured:
        log.exception("Course outline service is not configured")
        return Response(
            {"detail": "Course outline service is not configured."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return Response(outline_data, status=status.HTTP_200_OK)


@extend_schema(
    operation_id="course_variant_runs_v3",
    description="Fetch variant runs for a course(s) matching the specified filters.",
    parameters=[
        OpenApiParameter(
            name="course_id",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            required=True,
            many=True,
            description="Course ID(s) to use",
        ),
        OpenApiParameter(
            name="contract",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            required=True,
            description="Contract to filter by",
        ),
        OpenApiParameter(
            name="language",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="Language to retrieve",
        ),
        OpenApiParameter(
            name="industry",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="Industry focus to retrieve",
        ),
        OpenApiParameter(
            name="length",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="Language to retrieve",
        ),
    ],
    responses={
        200: CourseVariantRunsResponseSerializer(many=True),
        400: inline_serializer(
            name="CourseVariantRunBadRequestSerializer",
            fields={"detail": serializers.CharField()},
        ),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_course_variant_runs(request):
    """Get the variant runs for a course with filtering"""

    course_ids = request.query_params.getlist("course_id")
    contract = request.query_params.get("contract", None)
    language = request.query_params.get("language", "en")
    length = request.query_params.get("length", "")
    industry = request.query_params.get("industry", "")

    if not course_ids:
        return Response(
            {"detail": "Must specify courses to fetch."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not contract:
        return Response(
            {"detail": "Must specify contract."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        course_ids = [int(course_id) for course_id in course_ids]
        contract = int(contract)
    except ValueError:
        return Response(
            {"detail": "Must specify valid contract and/or course ID(s)."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if (
        not request.user.is_superuser
        and not request.user.b2b_contracts.filter(id=contract).exists()
    ) or (
        request.user.is_superuser
        and not ContractPage.objects.filter(id=contract).exists()
    ):
        return Response(
            {"detail": "Must specify valid contract."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    courses = Course.objects.filter(pk__in=course_ids)

    if not courses.count():
        return Response(
            {
                "detail": "No courses found.",
                "course_ids": course_ids,
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    variant_filter = (
        Q(language=language) & Q(variant_length=length) & Q(variant_industry=industry)
    )

    output = courses.prefetch_related(
        Prefetch(
            "courseruns",
            queryset=get_enrollable_courseruns_qs()
            .filter(b2b_contract_id=contract)
            .filter(variant_filter),
        )
    )

    return Response(CourseVariantRunsResponseSerializer(output, many=True).data)


class IngestibleCourseViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Largely a copy of the v2 CourseViewSet, but with changes for ETL processes.

    The shape of the data returned should match the v2 CourseViewSet for the most
    part, but we won't support lookups or filtering or anything and the prefetch
    setup will be reduced (since this won't have to care about what the requesting
    user's contracts are for instance).
    """

    pagination_class = Pagination
    permission_classes = [
        IsEtlUser,
    ]
    serializer_class = IngestibleCourseWithCourseRunsSerializer

    def get_queryset(self):
        """Get the queryset, with a bunch of prefetching for related data."""

        queryset = Course.objects.select_related("page")
        # Use Prefetch for reverse GenericRelation (products on CourseRun)
        # 1. Get the ContentType object for the CourseRun model
        courserun_content_type = ContentType.objects.get_for_model(CourseRun)
        # 2. Create a Prefetch object to specify the queryset for the 'tags' relation
        # This internal queryset only fetches products related to the CourseRun content type
        courserun_product_queryset = Product.objects.filter(
            content_type=courserun_content_type
        )
        # 3. Use prefetch_related on main queryset, referencing the reverse relation's name (e.g., 'products')
        products_prefetch = Prefetch(
            "products",
            queryset=courserun_product_queryset,
            to_attr="prefetched_products",
        )
        modes_prefetch = Prefetch(
            "enrollment_modes",
            to_attr="prefetched_enrollment_modes",
        )
        course_runs_prefetch = Prefetch(
            "courseruns",
            queryset=CourseRun.all_objects.order_by("id").prefetch_related(
                modes_prefetch, products_prefetch
            ),
            to_attr="prefetched_courseruns",
        )
        queryset = queryset.prefetch_related(
            "departments", "in_programs", course_runs_prefetch
        )
        queryset = queryset.annotate(
            count_b2b_courseruns=Count("courseruns__b2b_contract__id")
        )
        queryset = queryset.annotate(count_courseruns=Count("courseruns"))
        queryset = queryset.annotate(
            verified_courserun_count=Count(
                "courseruns__enrollment_modes",
                filter=Q(
                    courseruns__enrollment_modes__mode_slug=EDX_ENROLLMENT_VERIFIED_MODE
                ),
            )
        )

        return queryset.order_by("title").distinct()
