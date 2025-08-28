"""CMS app serializers"""

from __future__ import annotations

import bleach
from django.templatetags.static import static
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

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

    def get_effort(self, instance) -> str | None:
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

    def _get_financial_assistance_url(self, page, slug):
        """Helper method to construct financial assistance URL"""
        return f"{page.get_url()}{slug}/" if page and slug else ""

    @extend_schema_field(serializers.URLField)
    def get_financial_assistance_form_url(self, instance):
        """
        Returns URL of the Financial Assistance Form.
        Optimized version with reduced database queries.
        """
        # Early return if no programs
        if not instance.product.programs:
            # Check for course-specific form first
            financial_assistance_page = FlexiblePricingRequestForm.objects.filter(
                selected_course=instance.product
            ).first()
            
            if financial_assistance_page is None:
                # Check for child form
                financial_assistance_page = (
                    instance.get_children()
                    .type(FlexiblePricingRequestForm)
                    .live()
                    .first()
                )
            
            return (
                self._get_financial_assistance_url(instance, financial_assistance_page.slug)
                if financial_assistance_page
                else ""
            )

        # Build list of all valid program IDs efficiently
        program_ids = [program.id for program in instance.product.programs]
        
        # Collect related program IDs using list comprehension
        related_program_ids = [
            related_program.id
            for program in instance.product.programs
            for related_program in program.related_programs
        ]
        
        all_program_ids = program_ids + related_program_ids

        # Single query to find program page with children prefetched
        program_page = (
            ProgramPage.objects
            .filter(program_id__in=program_ids)
            .prefetch_related(
                'get_children__flexiblepricingrequestform'
            )
            .first()
        )

        # Check for program page child form first (highest precedence)
        if program_page:
            financial_assistance_page = (
                program_page.get_children()
                .type(FlexiblePricingRequestForm)
                .live()
                .first()
            )
            if financial_assistance_page:
                return self._get_financial_assistance_url(program_page, financial_assistance_page.slug)

        # Single optimized query for form by program selection
        financial_assistance_page = (
            FlexiblePricingRequestForm.objects
            .filter(selected_program_id__in=all_program_ids)
            .select_related('selected_program')
            .first()
        )

        if financial_assistance_page:
            # If form is for a different program, get its page URL
            if financial_assistance_page.selected_program_id not in program_ids:
                try:
                    program_page = ProgramPage.objects.get(
                        program=financial_assistance_page.selected_program
                    )
                    return self._get_financial_assistance_url(program_page, financial_assistance_page.slug)
                except ProgramPage.DoesNotExist:
                    pass
            else:
                # Use current instance URL if form is for current course's program
                return self._get_financial_assistance_url(instance, financial_assistance_page.slug)

                # Check for course-specific form
        financial_assistance_page = FlexiblePricingRequestForm.objects.filter(
            selected_course=instance.product
        ).first()

        if financial_assistance_page is None:
            # Check for child form as last resort
            financial_assistance_page = (
                instance.get_children()
                .type(FlexiblePricingRequestForm)
                .live()
                .first()
            )

        return (
            self._get_financial_assistance_url(instance, financial_assistance_page.slug)
            if financial_assistance_page
            else ""
        )

    def get_current_price(self, instance) -> int | None:
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

    def _get_financial_assistance_url(self, page, slug):
        """Helper method to construct financial assistance URL"""
        return f"{page.get_url()}{slug}/" if page and slug else ""

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
        Optimized version with reduced database queries.
        """
        # Check for form directly linked to this program first
        financial_assistance_page = (
            FlexiblePricingRequestForm.objects
            .filter(selected_program_id=instance.program.id)
            .live()
            .first()
        )
        
        # Check for child form if no direct link found
        if financial_assistance_page is None:
            page_children = instance.get_children()
            if page_children is not None:
                financial_assistance_page = (
                    page_children.type(FlexiblePricingRequestForm).live().first()
                )
        
        # Check related programs if no form found yet
        if (financial_assistance_page is None and
            len(instance.program.related_programs) > 0):
            
            related_program_ids = [
                rp.id for rp in instance.program.related_programs
            ]
            
            financial_assistance_page = (
                FlexiblePricingRequestForm.objects
                .filter(selected_program_id__in=related_program_ids)
                .select_related("selected_program")
                .live()
                .first()
            )

            if financial_assistance_page is not None:
                # Get the program page for the related program
                try:
                    program_page = ProgramPage.objects.get(
                        program=financial_assistance_page.selected_program
                    )
                    return self._get_financial_assistance_url(program_page, financial_assistance_page.slug)
                except ProgramPage.DoesNotExist:
                    return ""

        return (
            self._get_financial_assistance_url(instance, financial_assistance_page.slug)
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
