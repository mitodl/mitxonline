"""
Course API Views version 3
"""

from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import (
    IsAuthenticated,
)
from rest_framework.response import Response

from courses.api import create_program_enrollments
from courses.constants import ENROLL_CHANGE_STATUS_UNENROLLED
from courses.models import (
    Program,
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
