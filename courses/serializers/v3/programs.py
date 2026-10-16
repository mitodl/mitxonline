from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers

from courses.models import (
    Program,
    ProgramEnrollment,
    ProgramRequirement,
    ProgramRequirementNodeType,
)
from courses.serializers.v3.certificates import ProgramCertificateSerializer


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
            "display_mode",
        ]


@extend_schema_serializer(component_name="V3ProgramTrack")
class ProgramTrackSerializer(serializers.ModelSerializer):
    """A track node of a program's requirement tree."""

    class Meta:
        model = ProgramRequirement
        fields = ("id", "title")


@extend_schema_serializer(component_name="V3UserProgramEnrollment")
class ProgramEnrollmentSerializer(serializers.ModelSerializer):
    """
    Serializer for user program enrollments.
    """

    program = SimpleProgramSerializer(read_only=True)
    certificate = ProgramCertificateSerializer(allow_null=True, read_only=True)
    track = ProgramTrackSerializer(allow_null=True, read_only=True)

    class Meta:
        model = ProgramEnrollment
        fields = ("program", "certificate", "enrollment_mode", "track")


@extend_schema_serializer(component_name="V3ProgramEnrollmentTrack")
class ProgramEnrollmentTrackSerializer(serializers.Serializer):
    """Sets or clears the learner's chosen track on a program enrollment."""

    track = serializers.PrimaryKeyRelatedField(
        queryset=ProgramRequirement.objects.filter(
            node_type=ProgramRequirementNodeType.TRACK
        ),
        allow_null=True,
    )

    def validate_track(self, value):
        """Only a track of the enrollment's own program can be chosen."""
        if value is not None and value.program_id != self.instance.program_id:
            msg = "Must be a track of this program."
            raise serializers.ValidationError(msg)
        return value


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
