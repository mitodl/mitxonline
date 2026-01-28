from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers

from courses.models import (
    ProgramCertificate,
    ProgramEnrollment,
)


class ProgramCertificateSerializer(serializers.ModelSerializer):
    """ProgramCertificate model serializer"""

    class Meta:
        model = ProgramCertificate
        fields = ["uuid", "link"]


@extend_schema_serializer(component_name="V3UserProgramEnrollment")
class UserProgramEnrollmentSerializer(serializers.ModelSerializer):
    """
    Serializer for user program enrollments.
    """

    certificate = ProgramCertificateSerializer(allow_null=True, read_only=True)

    class Meta:
        model = ProgramEnrollment
        fields = ("program_id", "certificate")
