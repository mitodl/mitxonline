"""
Course API Views version 3
"""

import logging
import re

import django_filters
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Prefetch, Q
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
    IsAuthenticated,
)
from rest_framework.response import Response

from courses.api import create_program_enrollments, deactivate_run_enrollment
from courses.constants import COURSE_KEY_PATTERN, ENROLL_CHANGE_STATUS_UNENROLLED
from courses.models import (
    CourseRunEnrollment,
    Program,
    ProgramEnrollment,
)
from courses.serializers.v3.courses import (
    CourseOutlineResponseSerializer,
    CourseRunEnrollmentSerializer,
)
from courses.serializers.v3.programs import (
    ProgramEnrollmentCreateSerializer,
    ProgramEnrollmentSerializer,
)
from ecommerce.models import Product
from main import features
from openedx.api import get_edx_course_outline
from openedx.exceptions import EdxApiCourseOutlineError

log = logging.getLogger(__name__)


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
