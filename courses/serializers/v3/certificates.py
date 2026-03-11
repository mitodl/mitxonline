from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers

from courses.models import CourseRunCertificate, ProgramCertificate


@extend_schema_serializer(component_name="V3ProgramCertificate")
class ProgramCertificateSerializer(serializers.ModelSerializer):
    """ProgramCertificate model serializer"""

    class Meta:
        model = ProgramCertificate
        fields = ["uuid", "link"]


@extend_schema_serializer(component_name="V3CourseRunCertificate")
class CourseRunCertificateSerializer(serializers.ModelSerializer):
    """CourseRunCertificate model serializer"""

    class Meta:
        model = CourseRunCertificate
        fields = ["uuid", "link"]
