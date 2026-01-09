"""
Serializers for Wagtail API Schema
"""

import bleach
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from cms.models import CoursePage, ProgramPage
from courses.serializers.v2.courses import CourseSerializer
from courses.serializers.v2.programs import ProgramSerializer


class SignatoryItemSerializer(serializers.Serializer):
    """
    Serializer for signatory items used in certificate pages.
    """

    name = serializers.CharField()
    title_1 = serializers.CharField()
    title_2 = serializers.CharField()
    title_3 = serializers.CharField()
    organization = serializers.CharField()
    signature_image = serializers.CharField()  # or serializers.URLField() if full URLs


class FeatureImageSerializer(serializers.Serializer):
    """
    Serializer for feature images used in course pages.
    """

    title = serializers.CharField()
    image_url = serializers.URLField()
    height = serializers.IntegerField()
    width = serializers.IntegerField()


class TopicSerializer(serializers.Serializer):
    """
    Serializer for topics used in course pages.
    """

    name = serializers.CharField()
    parent = serializers.CharField(required=False)


class FacultySerializer(serializers.Serializer):
    """
    Serializer for faculty details used in course pages.
    """

    id = serializers.IntegerField()
    instructor_name = serializers.CharField()
    instructor_title = serializers.CharField()
    instructor_bio_short = serializers.CharField()
    instructor_bio_long = serializers.CharField()
    feature_image_src = serializers.CharField()


class PriceItemSerializer(serializers.Serializer):
    """
    Serializer for price items used in course pages.
    """

    type = serializers.CharField()
    value = serializers.DictField()
    id = serializers.UUIDField()


class OverrideValueSerializer(serializers.Serializer):
    """
    Serializer for override values used in certificate pages.
    """

    readable_id = serializers.CharField()
    CEUs = serializers.DecimalField(max_digits=5, decimal_places=2)


class OverrideSerializer(serializers.Serializer):
    """
    Serializer for overrides used in certificate pages.
    """

    type = serializers.CharField()
    value = OverrideValueSerializer()
    id = serializers.CharField()


class PageMetaSerializer(serializers.Serializer):
    """
    Serializer for page metadata used in various Wagtail pages.
    """

    type = serializers.CharField()
    detail_url = serializers.URLField()
    html_url = serializers.URLField()
    slug = serializers.CharField()
    show_in_menus = serializers.BooleanField()
    seo_title = serializers.CharField(allow_blank=True)
    search_description = serializers.CharField(allow_blank=True)
    first_published_at = serializers.DateTimeField(allow_null=True)
    alias_of = serializers.CharField(allow_null=True)
    locale = serializers.CharField()
    live = serializers.BooleanField()
    last_published_at = serializers.DateTimeField(allow_null=True)


class PageSerializer(serializers.Serializer):
    """
    Serializer for individual Wagtail pages.
    """

    id = serializers.IntegerField()
    title = serializers.CharField()
    meta = PageMetaSerializer()


class PageListMetaSerializer(serializers.Serializer):
    """
    Serializer for metadata of a list of Wagtail pages.
    """

    total_count = serializers.IntegerField()


class PageListSerializer(serializers.Serializer):
    """
    Serializer for a list of Wagtail pages.
    """

    meta = PageListMetaSerializer()
    items = PageSerializer(many=True)


class CertificatePageSerializer(serializers.Serializer):
    """
    Serializer for certificate pages, including overrides and signatory items.
    """

    id = serializers.IntegerField()
    meta = PageMetaSerializer()
    title = serializers.CharField()
    product_name = serializers.CharField()
    CEUs = serializers.CharField()  # assuming it's returned as a string
    overrides = OverrideSerializer(many=True)
    signatory_items = SignatoryItemSerializer(many=True)


class CertificatePageListSerializer(serializers.Serializer):
    """
    Serializer for a list of certificate pages.
    """

    meta = PageListMetaSerializer()
    items = CertificatePageSerializer(many=True)


class CoursePageItemSerializer(serializers.ModelSerializer):
    """
    Serializer for individual course page items, including all relevant fields.
    """

    class Meta:
        model = CoursePage
        fields = [
            "id",
            "meta",
            "title",
            "description",
            "length",
            "effort",
            "min_weekly_hours",
            "max_weekly_hours",
            "min_weeks",
            "max_weeks",
            "price",
            "min_price",
            "max_price",
            "prerequisites",
            "faq_url",
            "about",
            "what_you_learn",
            "feature_image",
            "video_url",
            "faculty_section_title",
            "faculty",
            "certificate_page",
            "course_details",
            "topic_list",
            "include_in_learn_catalog",
            "ingest_content_files_for_ai",
        ]

        # NOTE: We use this serializer for schema generation only,
        # And only for GET requests, in which all fields are returned.
        extra_kwargs = {field: {"required": True} for field in fields}

    price = PriceItemSerializer(many=True)
    meta = PageMetaSerializer()
    feature_image = FeatureImageSerializer()
    faculty = FacultySerializer(many=True)
    certificate_page = CertificatePageSerializer(allow_null=True)
    course_details = CourseSerializer()
    topic_list = TopicSerializer(many=True)


class CoursePageListSerializer(serializers.Serializer):
    """
    Serializer for a list of course pages, including metadata and items.
    """

    meta = PageListMetaSerializer()
    items = CoursePageItemSerializer(many=True)


class ProgramPageItemSerializer(serializers.ModelSerializer):
    """
    Serializer for individual program page items, including all relevant fields.
    """

    description = serializers.SerializerMethodField()

    class Meta:
        model = ProgramPage
        fields = [
            "id",
            "meta",
            "title",
            "description",
            "length",
            "effort",
            "min_weekly_hours",
            "max_weekly_hours",
            "min_weeks",
            "max_weeks",
            "price",
            "min_price",
            "max_price",
            "prerequisites",
            "faq_url",
            "about",
            "what_you_learn",
            "feature_image",
            "video_url",
            "faculty_section_title",
            "faculty",
            "certificate_page",
            "program_details",
        ]

        # NOTE: We use this serializer for schema generation only,
        # And only for GET requests, in which all fields are returned.
        extra_kwargs = {field: {"required": True} for field in fields}

    @extend_schema_field(str)
    def get_description(self, instance):
        """Get cleaned description text"""
        if instance.description:
            return bleach.clean(instance.description, tags=[], strip=True)
        return ""

    meta = PageMetaSerializer()
    price = PriceItemSerializer(many=True)
    feature_image = FeatureImageSerializer()
    faculty = FacultySerializer(many=True)
    certificate_page = CertificatePageSerializer()
    program_details = ProgramSerializer()


class ProgramPageListSerializer(serializers.Serializer):
    """
    Serializer for a list of program pages, including metadata and items.
    """

    meta = PageListMetaSerializer()
    items = ProgramPageItemSerializer(many=True)
