"""CMS app serializers"""

import bleach
from django.templatetags.static import static
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from cms import models
from cms.api import get_wagtail_img_src
from cms.models import FlexiblePricingRequestForm, ProgramPage
from courses.constants import DEFAULT_COURSE_IMG_PATH


class BaseCoursePageSerializer(serializers.ModelSerializer):
    """Course page model serializer"""

    feature_image_src = serializers.SerializerMethodField()
    page_url = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    effort = serializers.SerializerMethodField()
    length = serializers.SerializerMethodField()

    @extend_schema_field(str)
    def get_feature_image_src(self, instance):
        """Serializes the source of the feature_image"""
        feature_img_src = None
        if hasattr(instance, "feature_image"):
            feature_img_src = get_wagtail_img_src(instance.feature_image)

        return feature_img_src or static(DEFAULT_COURSE_IMG_PATH)

    @extend_schema_field(serializers.URLField)
    def get_page_url(self, instance):
        return instance.get_url()

    @extend_schema_field(str)
    def get_description(self, instance):
        return bleach.clean(instance.description, tags=[], strip=True)

    @extend_schema_field(str)
    def get_effort(self, instance):
        return (
            bleach.clean(instance.effort, tags=[], strip=True)
            if instance.effort
            else None
        )

    @extend_schema_field(str)
    def get_length(self, instance):
        return (
            bleach.clean(instance.length, tags=[], strip=True)
            if instance.length
            else None
        )

    class Meta:
        model = models.CoursePage
        fields = [
            "feature_image_src",
            "page_url",
            "description",
            "live",
            "length",
            "effort",
        ]


class CoursePageSerializer(BaseCoursePageSerializer):
    """Course page model serializer"""

    financial_assistance_form_url = serializers.SerializerMethodField()
    instructors = serializers.SerializerMethodField()
    current_price = serializers.SerializerMethodField()

    @extend_schema_field(serializers.URLField)
    def get_financial_assistance_form_url(self, instance):
        """
        Returns URL of the Financial Assistance Form.
        """
        financial_assistance_page = None
        if instance.product.programs:
            valid_program_objs = [program for program in instance.product.programs]  # noqa: C416
            valid_related_programs = []

            for valid_program in valid_program_objs:
                for valid_related_program in valid_program.related_programs:
                    valid_related_programs.append(valid_related_program)  # noqa: PERF402

            valid_program_objs.extend(valid_related_programs)

            program_page = ProgramPage.objects.filter(
                program_id__in=[program.id for program in valid_program_objs]
            ).first()

            # for courses in program, financial assistance form from program should take precedence if exist
            if program_page:
                financial_assistance_page = (
                    program_page.get_children()
                    .type(FlexiblePricingRequestForm)
                    .live()
                    .first()
                )
                if financial_assistance_page:
                    return f"{program_page.get_url()}{financial_assistance_page.slug}/"

            financial_assistance_page = FlexiblePricingRequestForm.objects.filter(
                selected_program__in=valid_program_objs
            ).first()

        if financial_assistance_page is None:
            financial_assistance_page = FlexiblePricingRequestForm.objects.filter(
                selected_course=instance.product
            ).first()

        if financial_assistance_page is None:
            financial_assistance_page = (
                instance.get_children().type(FlexiblePricingRequestForm).live().first()
            )

        return (
            f"{instance.get_url()}{financial_assistance_page.slug}/"
            if financial_assistance_page
            else ""
        )

    @extend_schema_field(int)
    def get_current_price(self, instance):
        relevant_product = (
            instance.product.active_products.filter().order_by("-price").first()
            if instance.product.active_products
            else None
        )
        return relevant_product.price if relevant_product else None

    @extend_schema_field(list)
    def get_instructors(self, instance):
        members = [
            member.linked_instructor_page
            for member in instance.linked_instructors.all()
        ]
        returnable_members = []

        for member in members:
            returnable_members.append(  # noqa: PERF401
                {
                    "name": member.instructor_name,
                    "description": bleach.clean(
                        member.instructor_bio_short, tags=[], strip=True
                    ),
                }
            )

        return returnable_members

    class Meta:
        model = models.CoursePage
        fields = BaseCoursePageSerializer.Meta.fields + [  # noqa: RUF005
            "financial_assistance_form_url",
            "current_price",
            "instructors",
        ]


class ProgramPageSerializer(serializers.ModelSerializer):
    """Program page model serializer"""

    feature_image_src = serializers.SerializerMethodField()
    page_url = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    financial_assistance_form_url = serializers.SerializerMethodField()

    @extend_schema_field(str)
    def get_feature_image_src(self, instance):
        """Serializes the source of the feature_image"""
        feature_img_src = None
        if hasattr(instance, "feature_image"):
            feature_img_src = get_wagtail_img_src(instance.feature_image)

        return feature_img_src or static(DEFAULT_COURSE_IMG_PATH)

    @extend_schema_field(serializers.URLField)
    def get_page_url(self, instance):
        return instance.get_url()

    @extend_schema_field(str)
    def get_price(self, instance):
        return instance.price[0].value["text"] if len(instance.price) > 0 else None

    @extend_schema_field(serializers.URLField)
    def get_financial_assistance_form_url(self, instance):
        """
        Returns URL of the Financial Assistance Form.
        """
        financial_assistance_page = (
            FlexiblePricingRequestForm.objects.filter(
                selected_program_id=instance.program.id
            )
            .live()
            .first()
        )
        page_children = instance.get_children()
        if (financial_assistance_page is None) and (page_children is not None):
            financial_assistance_page = (
                page_children.type(FlexiblePricingRequestForm).live().first()
            )
        if (financial_assistance_page is None) & (
            len(instance.program.related_programs) > 0
        ):
            financial_assistance_page = (
                FlexiblePricingRequestForm.objects.filter(
                    selected_program__in=instance.program.related_programs
                )
                .select_related("selected_program")
                .live()
                .first()
            )

            if financial_assistance_page is None:
                return ""

            program_page = ProgramPage.objects.filter(
                program=financial_assistance_page.selected_program
            ).get()
            return f"{program_page.get_url()}{financial_assistance_page.slug}/"

        return (
            f"{instance.get_url()}{financial_assistance_page.slug}/"
            if financial_assistance_page
            else ""
        )

    class Meta:
        model = models.ProgramPage
        fields = [
            "feature_image_src",
            "page_url",
            "financial_assistance_form_url",
            "description",
            "live",
            "length",
            "effort",
            "price",
        ]


class InstructorPageSerializer(serializers.ModelSerializer):
    """Instructor page model serializer"""

    feature_image_src = serializers.SerializerMethodField()

    @extend_schema_field(str)
    def get_feature_image_src(self, instance):
        """Serializes the source of the feature_image"""
        feature_img_src = None
        if hasattr(instance, "feature_image"):
            feature_img_src = get_wagtail_img_src(instance.feature_image)

        return feature_img_src or static(DEFAULT_COURSE_IMG_PATH)

    class Meta:
        model = models.InstructorPage
        fields = [
            "id",
            "instructor_name",
            "instructor_title",
            "instructor_bio_short",
            "instructor_bio_long",
            "feature_image_src",
        ]
        read_only_fields = [
            "id",
            "instructor_name",
            "instructor_title",
            "instructor_bio_short",
            "instructor_bio_long",
            "feature_image_src",
        ]
