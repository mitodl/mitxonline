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
        """Get the page URL for the instance."""
        return instance.get_url()

    @extend_schema_field(str)
    def get_description(self, instance):
        """Get cleaned description text."""
        return bleach.clean(instance.description, tags={}, strip=True)

    def get_effort(self, instance) -> str | None:
        """Get cleaned effort text."""
        return (
            bleach.clean(instance.effort, tags={}, strip=True)
            if instance.effort
            else None
        )

    @extend_schema_field(str)
    def get_length(self, instance):
        """Get cleaned length text."""
        return (
            bleach.clean(instance.length, tags={}, strip=True)
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

    def _get_course_specific_form(self, instance):
        """Get financial assistance form specific to the course."""
        return FlexiblePricingRequestForm.objects.filter(
            selected_course=instance.product
        ).first()

    def _get_child_form(self, instance):
        """Get financial assistance form from child pages."""
        return instance.get_children().type(FlexiblePricingRequestForm).live().first()

    def _get_program_form(self, program_ids, all_program_ids):
        """Get financial assistance form from program relationships."""
        # Check for program page with child form first
        program_page = (
            ProgramPage.objects.filter(program_id__in=program_ids)
            .prefetch_related("get_children__flexiblepricingrequestform")
            .first()
        )

        if program_page:
            child_form = (
                program_page.get_children()
                .type(FlexiblePricingRequestForm)
                .live()
                .first()
            )
            if child_form:
                return program_page, child_form

        # Check for form by program selection
        if all_program_ids:
            form = (
                FlexiblePricingRequestForm.objects.filter(
                    selected_program_id__in=all_program_ids
                )
                .select_related("selected_program")
                .live()
                .first()
            )
            if form:
                return None, form

        return None, None

    def _get_program_ids(self, programs):
        """Extract program IDs and related program IDs."""
        program_ids = [program.id for program in programs]
        related_program_ids = []
        for program in programs:
            related_programs = program.related_programs
            related_program_ids.extend([rp.id for rp in related_programs])

        return program_ids, program_ids + related_program_ids

    def _handle_form_logic(self, instance, program_page, form, program_ids):
        """
        Handle the form logic and return appropriate URL.

        Priority:
        1. Use program page if available (form is child of program page)
        2. If form is for a different program, use that program's page
        3. If form is for current program, use current instance page
        4. Return empty string if no valid page found
        """
        # Case 1: Form is a child of a program page
        if program_page:
            return self._get_financial_assistance_url(program_page, form.slug)

        # Case 2: Form is for a different program - find its page
        if form.selected_program_id not in program_ids:
            try:
                different_program_page = ProgramPage.objects.get(
                    program=form.selected_program
                )
                return self._get_financial_assistance_url(
                    different_program_page, form.slug
                )
            except ProgramPage.DoesNotExist:
                # If the different program doesn't have a page, fall through to default
                pass

        # Case 3: Form is for current program - use current instance
        if form.selected_program_id in program_ids:
            return self._get_financial_assistance_url(instance, form.slug)

        # Case 4: No valid page found
        return ""

    @extend_schema_field(serializers.URLField)
    def get_financial_assistance_form_url(self, instance):
        """
        Returns URL of the Financial Assistance Form.
        """
        if not hasattr(instance, "product") or not instance.product:
            return ""

        # Cache program IDs to avoid repeated access
        programs_relation = instance.product.programs
        programs = list(programs_relation) if programs_relation else []

        if not programs:
            # Handle case with no programs
            form = self._get_course_specific_form(instance)
            if form is None:
                form = self._get_child_form(instance)
            return (
                self._get_financial_assistance_url(instance, form.slug) if form else ""
            )

        program_ids, all_program_ids = self._get_program_ids(programs)

        program_page, form = self._get_program_form(program_ids, all_program_ids)

        if form:
            result = self._handle_form_logic(instance, program_page, form, program_ids)
            if result:
                return result

        # Fallback to course-specific or child form
        form = self._get_course_specific_form(instance)
        if form is None:
            form = self._get_child_form(instance)

        return self._get_financial_assistance_url(instance, form.slug) if form else ""

    def get_current_price(self, instance) -> int | None:
        """Get the current price of the course product."""
        # Handle both QuerySet and prefetched list cases
        active_products = instance.product.active_products
        if active_products is None:
            return None

        try:
            # Convert to list and sort by price (descending)
            products_list = (
                list(active_products.all())
                if hasattr(active_products, "all")
                else list(active_products)
            )
            relevant_product = (
                max(products_list, key=lambda p: p.price) if products_list else None
            )
        except (AttributeError, TypeError):
            relevant_product = None

        return relevant_product.price if relevant_product else None

    @extend_schema_field(list)
    def get_instructors(self, instance):
        """Get instructor information"""
        linked_instructors = instance.linked_instructors

        # Use the prefetched results directly - this should not trigger additional queries
        # since we've prefetched with Prefetch object in the view
        instructor_links = list(linked_instructors.all())

        return [
            {
                "name": getattr(link.linked_instructor_page, "instructor_name", ""),
                "description": bleach.clean(
                    getattr(link.linked_instructor_page, "instructor_bio_short", ""),
                    tags={},
                    strip=True,
                )
                if getattr(link.linked_instructor_page, "instructor_bio_short", None)
                else "",
            }
            for link in instructor_links
            if link.linked_instructor_page
        ]

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
    description = serializers.SerializerMethodField()

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
        """Get the page URL for the instance."""
        return instance.get_url()

    @extend_schema_field(str)
    def get_description(self, instance):
        """The description shown on the home page and product page."""
        if instance.description:
            return bleach.clean(instance.description, tags={}, strip=True)
        return ""

    @extend_schema_field(str)
    def get_price(self, instance):
        """Get the price text from the program page."""
        if hasattr(instance, "price") and instance.price:
            return (
                instance.price[0].value.get("text") if len(instance.price) > 0 else None
            )
        return None

    @extend_schema_field(serializers.URLField)
    def get_financial_assistance_form_url(self, instance):
        """
        Returns URL of the Financial Assistance Form.
        """
        # Check for form directly linked to this program first
        financial_assistance_page = (
            FlexiblePricingRequestForm.objects.filter(
                selected_program_id=instance.program.id
            )
            .live()
            .first()
        )

        # Check for child form if no direct link found
        if financial_assistance_page is None:
            page_children = instance.get_children()
            if page_children.exists():
                financial_assistance_page = (
                    page_children.type(FlexiblePricingRequestForm).live().first()
                )

        # Check related programs if no form found yet
        if financial_assistance_page is None:
            related_programs = instance.program.related_programs

            if related_programs:
                related_program_ids = [rp.id for rp in related_programs]

                financial_assistance_page = (
                    FlexiblePricingRequestForm.objects.filter(
                        selected_program_id__in=related_program_ids
                    )
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
                        return self._get_financial_assistance_url(
                            program_page, financial_assistance_page.slug
                        )
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
