"""Serializers for certificate data."""

from rest_framework import serializers
from wagtail.api.v2.serializers import PageSerializer

from courses.models import BaseCertificate, CourseRunCertificate, ProgramCertificate
from users.serializers import UserSerializer


class BaseCertificateSerializer(serializers.ModelSerializer):
    """Serializer for the shared BaseCertificate model"""

    user = UserSerializer()
    certificate_page = serializers.SerializerMethodField()

    def get_certificate_page(self, instance):
        """
        Retrieve the certificate page. For certificates, we want to return the
        page data for the specific revision of the page we're working with, or
        we may display incorrect data to the end user. (The implementation of
        this is the same across both certificate types, even though the field
        definition itself is slightly different.)
        """

        if hasattr(instance, "certificate_page_revision"):
            cert = instance.certificate_page_revision.as_object()

            # This should change once the Wagtail API stuff gets merged.
            return PageSerializer(cert).data

        return None

    class Meta:
        """Meta options for the serializer."""

        model = BaseCertificate
        fields = [
            "user",
            "uuid",
            "is_revoked",
            "certificate_page",
        ]
        readonly_fields = [
            "user",
            "uuid",
            "is_revoked",
            "certificate_page",
        ]


class CourseRunCertificateSerializer(BaseCertificateSerializer):
    """Serializer for course certificates."""

    class Meta:
        """Meta options for the serializer."""

        model = CourseRunCertificate
        fields = [
            *BaseCertificateSerializer.Meta.fields,
            "course_run",
            "certificate_page_revision",
        ]
        readonly_fields = [
            *BaseCertificateSerializer.Meta.readonly_fields,
            "course_run",
            "certificate_page_revision",
        ]


class ProgramCertificateSerializer(BaseCertificateSerializer):
    """Serializer for course certificates."""

    class Meta:
        """Meta options for the serializer."""

        model = ProgramCertificate
        fields = [
            *BaseCertificateSerializer.Meta.fields,
            "program",
            "certificate_page_revision",
        ]
        readonly_fields = [
            *BaseCertificateSerializer.Meta.readonly_fields,
            "program",
            "certificate_page_revision",
        ]
