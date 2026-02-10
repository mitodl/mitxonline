"""
Course API Views version 3
"""

import django_filters
from django.conf import settings
from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import (
    IsAuthenticated,
)
from rest_framework.response import Response

from courses.api import create_program_enrollments
from courses.api import deactivate_run_enrollment
from courses.constants import ENROLL_CHANGE_STATUS_UNENROLLED
from courses.models import (
    Program,
    CourseRunEnrollment,
    ProgramEnrollment,
)
from courses.serializers.v3.programs import (
    ProgramEnrollmentCreateSerializer,
    ProgramEnrollmentSerializer,
)
from courses.serializers.v3.programs import ProgramEnrollmentSerializer
from courses.serializers.v3.courses import CourseRunEnrollmentSerializer
from courses.serializers.v3.programs import ProgramEnrollmentSerializer
from main import features


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
        .prefetch_related("run__course")
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
            enrollment.deactivate_and_save(ENROLL_CHANGE_STATUS_UNENROLLED)

        return Response(status=status.HTTP_204_NO_CONTENT)
