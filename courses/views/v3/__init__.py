"""
Course API Views version 3
"""

from django.db.models import Q
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import (
    IsAuthenticated,
)
from rest_framework.response import Response

from courses.api import create_program_enrollments
from courses.constants import ENROLL_CHANGE_STATUS_UNENROLLED
from courses.models import (
    ProgramEnrollment,
)
from courses.serializers.v3.programs import (
    ProgramEnrollmentCreateSerializer,
    ProgramEnrollmentSerializer,
)


@extend_schema_view(
    list=extend_schema(operation_id="v3_program_enrollments_list"),
    retrieve=extend_schema(operation_id="v3_program_enrollments_retrieve"),
    create=extend_schema(operation_id="v3_program_enrollments_create"),
)
class UserProgramEnrollmentsViewSet(
    mixins.CreateModelMixin,
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
        existing_enrollment = ProgramEnrollment.objects.filter(
            user=request.user,
            program=program,
        ).first()

        if existing_enrollment:
            response_serializer = ProgramEnrollmentSerializer(existing_enrollment)
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        # Create the enrollment
        enrollment = self.perform_create(request.user, program)
        response_serializer = ProgramEnrollmentSerializer(enrollment)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    def perform_create(self, user, program):
        """
        Create a program enrollment via courses.api.

        Uses the default enrollment mode (audit).
        """
        enrollments = create_program_enrollments(user, [program])
        if not enrollments:
            raise ValueError("Failed to create program enrollment.")  # noqa: EM101
        return enrollments[0]
