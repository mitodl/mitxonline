"""
Course API Views version 2
"""

from django.db.models import Q
from drf_spectacular.utils import extend_schema_view
from rest_framework import viewsets
from rest_framework.permissions import (
    IsAuthenticated,
)

from courses.constants import ENROLL_CHANGE_STATUS_UNENROLLED
from courses.models import (
    ProgramEnrollment,
)
from courses.serializers.v3.programs import UserProgramEnrollmentSerializer


@extend_schema_view(operation_id="v3_program_enrollments")
class UserProgramEnrollmentsViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for user program enrollments with v3 serializers."""

    permission_classes = [IsAuthenticated]

    serializer_class = UserProgramEnrollmentSerializer

    lookup_field = "program_id"

    def get_queryset(self):
        """Get the queryset for the current user"""
        request = self.request
        return (
            ProgramEnrollment.objects.prefetch_related(
                "program",
                "program__page",
            )
            .filter(user=request.user)
            .filter(~Q(change_status=ENROLL_CHANGE_STATUS_UNENROLLED))
            .order_by("-id")
        )
