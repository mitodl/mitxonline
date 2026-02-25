from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers

from courses.models import (
    Program,
    ProgramCertificate,
    ProgramEnrollment,
)


@extend_schema_serializer(
    component_name="V3SimpleProgram",
)
class SimpleProgramSerializer(serializers.ModelSerializer):
    """Program Model Serializer v2"""

    class Meta:
        model = Program
        fields = [
            "title",
            "readable_id",
            "id",
            "program_type",
            "live",
        ]


@extend_schema_serializer(component_name="V3ProgramCertificate")
class ProgramCertificateSerializer(serializers.ModelSerializer):
    """ProgramCertificate model serializer"""

    class Meta:
        model = ProgramCertificate
        fields = ["uuid", "link"]


@extend_schema_serializer(component_name="V3UserProgramEnrollment")
class ProgramEnrollmentSerializer(serializers.ModelSerializer):
    """
    Serializer for user program enrollments.
    """

    program = SimpleProgramSerializer(read_only=True)
    certificate = ProgramCertificateSerializer(allow_null=True, read_only=True)

    class Meta:
        model = ProgramEnrollment
        fields = ("program", "certificate", "enrollment_mode")


@extend_schema_serializer(component_name="V3ProgramEnrollmentRequest")
class ProgramEnrollmentCreateSerializer(serializers.Serializer):
    """
    Serializer for creating a program enrollment.
    Accepts a program_id and validates it corresponds to a live program.
    """

    program_id = serializers.IntegerField(write_only=True)

    def validate_program_id(self, value):
        """Validate that the program_id corresponds to a live program."""
        try:
            program = Program.objects.get(id=value, live=True)
        except Program.DoesNotExist as err:
            msg = f"Invalid program_id: {value}"
            raise serializers.ValidationError(msg) from err
        self.program = program
        return value
