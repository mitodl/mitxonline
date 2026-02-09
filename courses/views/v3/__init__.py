"""
Course API Views version 2
"""

from django.db.models import Q
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.permissions import (
    IsAuthenticated,
)

from courses.constants import ENROLL_CHANGE_STATUS_UNENROLLED
from courses.models import (
    ProgramEnrollment,
)
from courses.serializers.v3.programs import ProgramEnrollmentSerializer


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
