"""
Course API Views version 2
"""

import django_filters
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.permissions import (
    IsAuthenticated,
)

from courses.constants import ENROLL_CHANGE_STATUS_UNENROLLED
from courses.models import (
    CourseRunEnrollment,
    ProgramEnrollment,
)
from courses.serializers.v3.courses import CourseRunEnrollmentSerializer
from courses.serializers.v3.programs import ProgramEnrollmentSerializer


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
)
class UserEnrollmentsApiViewSet(viewsets.ReadOnlyModelViewSet):
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
        .prefetch("certificate")
        .order_by("id")
    )

    def get_queryset(self):
        """Get the queryset for user enrollments."""
        return super().get_queryset().filter(user=self.request.user)

    def get_serializer_context(self):
        """Get the serializer context."""
        return {"user": self.request.user}


@extend_schema_view(
    list=extend_schema(operation_id="v3_program_enrollments_list"),
    retrieve=extend_schema(operation_id="v3_program_enrollments_retrieve"),
)
class UserProgramEnrollmentsViewSet(viewsets.ReadOnlyModelViewSet):
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
