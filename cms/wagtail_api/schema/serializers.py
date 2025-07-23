"""
Serializers for Wagtail API Schema
"""

from rest_framework import serializers

from courses.serializers.v2.courses import CourseSerializer
from courses.serializers.v2.programs import ProgramSerializer


class SignatoryItemSerializer(serializers.Serializer):
    """
    Serializer for signatory items used in certificate pages.
    """

    name = serializers.CharField()
    title_1 = serializers.CharField()
    title_2 = serializers.CharField()
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


class CoursePageItemSerializer(serializers.Serializer):
    """
    Serializer for individual course page items, including all relevant fields.
    """

    id = serializers.IntegerField()
    meta = PageMetaSerializer()
    title = serializers.CharField()
    description = serializers.CharField()
    length = serializers.CharField()
    effort = serializers.CharField()
    min_weekly_hours = serializers.CharField()
    max_weekly_hours = serializers.CharField()
    min_weeks = serializers.IntegerField()
    max_weeks = serializers.IntegerField()
    price = PriceItemSerializer(many=True)
    min_price = serializers.IntegerField()
    max_price = serializers.IntegerField()
    prerequisites = serializers.CharField()
    faq_url = serializers.CharField()
    about = serializers.CharField()
    what_you_learn = serializers.CharField()
    feature_image = FeatureImageSerializer()
    video_url = serializers.URLField()
    faculty_section_title = serializers.CharField()
    faculty = FacultySerializer(many=True)
    certificate_page = CertificatePageSerializer(allow_null=True)
    course_details = CourseSerializer()
    topic_list = TopicSerializer(many=True)
    include_in_learn_catalog = serializers.BooleanField()
    ingest_content_files_for_ai = serializers.BooleanField()


class CoursePageListSerializer(serializers.Serializer):
    """
    Serializer for a list of course pages, including metadata and items.
    """

    meta = PageListMetaSerializer()
    items = CoursePageItemSerializer(many=True)


class ProgramPageItemSerializer(serializers.Serializer):
    """
    Serializer for individual program page items, including all relevant fields.
    """

    id = serializers.IntegerField()
    meta = PageMetaSerializer()
    title = serializers.CharField()
    description = serializers.CharField()
    length = serializers.CharField()
    effort = serializers.CharField()
    min_weekly_hours = serializers.CharField()
    max_weekly_hours = serializers.CharField()
    min_weeks = serializers.IntegerField()
    max_weeks = serializers.IntegerField()
    price = PriceItemSerializer(many=True)
    min_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    max_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    prerequisites = serializers.CharField()
    faq_url = serializers.URLField()
    about = serializers.CharField()
    what_you_learn = serializers.CharField()
    feature_image = FeatureImageSerializer()
    video_url = serializers.URLField()
    faculty_section_title = serializers.CharField()
    faculty = FacultySerializer(many=True)
    certificate_page = CertificatePageSerializer()
    program_details = ProgramSerializer()


class ProgramPageListSerializer(serializers.Serializer):
    """
    Serializer for a list of program pages, including metadata and items.
    """

    meta = PageListMetaSerializer()
    items = ProgramPageItemSerializer(many=True)
