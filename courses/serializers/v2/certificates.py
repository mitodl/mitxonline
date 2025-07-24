"""Serializers for certificate data."""

from rest_framework import serializers
from rest_framework.reverse import reverse
from wagtail.api.v2.serializers import (
    PageHtmlUrlField,
    PageLocaleField,
)
from wagtail.models import Page

from cms.models import CertificatePage
from cms.wagtail_api.schema.serializers import (
    CertificatePageSerializer,
    PageMetaSerializer,
)
from courses.models import BaseCertificate, CourseRunCertificate, ProgramCertificate
from users.serializers import UserSerializer


class PageMetaModelSerializer(PageMetaSerializer, serializers.ModelSerializer):
    """Extends the PageMetaSerializer to work with a Page object"""

    type = serializers.SerializerMethodField()
    detail_url = serializers.SerializerMethodField()
    html_url = PageHtmlUrlField()
    locale = PageLocaleField()

    def get_type(self, instance):
        """
        Get the page type, in a more simple manner than Wagtail.

        The Wagtail version of this is PageTypeField, and it tries to modify the
        context, which we neither need nor is in the correct format for it.
        """

        if instance.specific_class is None:
            return None
        return (
            instance.specific_class._meta.app_label  # noqa: SLF001
            + "."
            + instance.specific_class.__name__
        )

    def get_detail_url(self, instance):
        """
        Get the detail URL, which should be the API call for this page.
        """

        return reverse("wagtailapi:pages:detail", kwargs={"pk": instance.id})

    class Meta:
        """Meta opts for the serializer."""

        model = Page
        fields = [
            "type",
            "detail_url",
            "html_url",
            "slug",
            "show_in_menus",
            "seo_title",
            "search_description",
            "first_published_at",
            "alias_of",
            "locale",
            "live",
            "last_published_at",
        ]
        read_only_fields = [
            "type",
            "detail_url",
            "html_url",
            "slug",
            "show_in_menus",
            "seo_title",
            "search_description",
            "first_published_at",
            "alias_of",
            "locale",
            "live",
            "last_published_at",
        ]


class CertificatePageModelSerializer(
    CertificatePageSerializer, serializers.ModelSerializer
):
    """Extends the CertificatePageSerializer to work with a model object."""

    meta = serializers.SerializerMethodField()

    def get_meta(self, instance):
        """Get page metadata."""

        return PageMetaModelSerializer(
            instance.page_ptr, context={"request": self.context["request"]}
        ).data

    class Meta:
        """Meta opts for the serializer."""

        model = CertificatePage
        fields = [
            "id",
            "meta",
            "title",
            "product_name",
            "CEUs",
            "overrides",
            "signatory_items",
        ]
        read_only_fields = [
            "id",
            "meta",
            "title",
            "product_name",
            "CEUs",
            "overrides",
            "signatory_items",
        ]


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

            return CertificatePageModelSerializer(
                cert, context={"request": self.context["request"]}
            ).data

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
        read_only_fields = [
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
        read_only_fields = [
            *BaseCertificateSerializer.Meta.read_only_fields,
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
        read_only_fields = [
            *BaseCertificateSerializer.Meta.read_only_fields,
            "program",
            "certificate_page_revision",
        ]
