from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers

from courses.models import CourseRunCertificate, ProgramCertificate
from courses.serializers.utils import validate_certificate_dates


@extend_schema_serializer(component_name="V3ProgramCertificate")
class ProgramCertificateSerializer(serializers.ModelSerializer):
    """ProgramCertificate model serializer"""

    def to_representation(self, instance):
        if not validate_certificate_dates(instance):
            return None
        return super().to_representation(instance)

    class Meta:
        model = ProgramCertificate
        fields = ["uuid", "link"]


@extend_schema_serializer(component_name="V3CourseRunCertificate")
class CourseRunCertificateSerializer(serializers.ModelSerializer):
    """CourseRunCertificate model serializer"""

    def to_representation(self, instance):
        if not validate_certificate_dates(instance):
            return None
        return super().to_representation(instance)

    class Meta:
        model = CourseRunCertificate
        fields = ["uuid", "link"]
