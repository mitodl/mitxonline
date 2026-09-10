"""CMS app serializers"""

from __future__ import annotations

import bleach
from drf_spectacular.utils import extend_schema_field
from mitol.common.utils.queryset import is_prefetched
from rest_framework import serializers

from cms import models
from cms.api import get_wagtail_img_src
from cms.models import FlexiblePricingRequestForm, ProgramPage
from main.utils import get_learn_product_url


class BaseCoursePageSerializer(serializers.ModelSerializer):
    """Course page model serializer"""

    feature_image_src = serializers.SerializerMethodField()
    page_url = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    effort = serializers.SerializerMethodField()
    length = serializers.SerializerMethodField()

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_feature_image_src(self, instance):
        """Serializes the source of the feature_image, or None if not set."""
        if hasattr(instance, "feature_image"):
            return get_wagtail_img_src(instance.feature_image) or None
        return None

    @extend_schema_field(serializers.URLField)
    def get_page_url(self, instance):
        """Get the Learn URL for the instance."""
        return get_learn_product_url("courses", instance.product.readable_id)

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

    # A plain attribute read. The view's queryset resolves it via
    # Course.objects.prefetch("financial_assistance_form_url"); CoursePage's
    # same-named cached_property is the fallback for non-API callers.
    # URLField, not CharField: it preserves the "format: uri" the previous
    # @extend_schema_field(URLField) put in the checked-in OpenAPI specs.
    financial_assistance_form_url = serializers.URLField(read_only=True)
    instructors = serializers.SerializerMethodField()
    current_price = serializers.SerializerMethodField()

    def get_current_price(self, instance) -> int | None:
        """Get the current price of the course product."""
        active_products = instance.product.active_products
        if not active_products:
            return None
        try:
            # Only call max if there are products
            relevant_product = max(active_products, key=lambda p: p.price)
        except (ValueError, AttributeError, TypeError):
            relevant_product = None
        return relevant_product.price if relevant_product else None

    @extend_schema_field(list)
    def get_instructors(self, instance):
        """Get instructor information"""
        # linked_instructors is always a related manager, so the old
        # hasattr(.., "all") test was always true and the select_related()
        # branch always ran - building a fresh queryset and ignoring any
        # prefetch cache, one query per page.
        #
        # Read the cache when it is there; keep select_related() for the
        # callers that do not prefetch (v1 courses, ecommerce), where dropping
        # it would turn one query into one per instructor link.
        if is_prefetched(instance, "linked_instructors"):
            instructor_links = instance.linked_instructors.all()
        else:
            instructor_links = instance.linked_instructors.select_related(
                "linked_instructor_page"
            ).all()

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
    list_price = serializers.SerializerMethodField()
    financial_assistance_form_url = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()

    def _get_financial_assistance_url(self, page, slug):
        """Helper method to construct financial assistance URL"""
        return f"{page.get_url()}{slug}/" if page and slug else ""

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_feature_image_src(self, instance):
        """Serializes the source of the feature_image, or None if not set."""
        if hasattr(instance, "feature_image"):
            return get_wagtail_img_src(instance.feature_image) or None
        return None

    @extend_schema_field(serializers.URLField)
    def get_page_url(self, instance):
        """Get the Learn URL for the instance."""
        return get_learn_product_url("programs", instance.product.readable_id)

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

    @extend_schema_field(serializers.DecimalField(max_digits=10, decimal_places=2))
    def get_list_price(self, instance):
        """Get the page list price or fall back to the linked program product price."""
        if instance.list_price is not None:
            return instance.list_price

        if instance.program is None:
            return None
        product = instance.program.active_product
        if product is None:
            return None
        return product.price

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

        # If a form is found via selected_program, prefer its parent page
        # (e.g., a course or program page) when constructing the URL. This
        # ensures that forms which are children of course pages but linked to
        # a program use the correct /courses/ URL instead of the program URL.
        if financial_assistance_page is not None:
            parent = financial_assistance_page.get_parent()
            if parent is not None:
                parent_page = getattr(parent, "specific", parent)
                return self._get_financial_assistance_url(
                    parent_page, financial_assistance_page.slug
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
            "include_in_learn_catalog",
            "length",
            "effort",
            "price",
            "list_price",
        ]


class InstructorPageSerializer(serializers.ModelSerializer):
    """Instructor page model serializer"""

    feature_image_src = serializers.SerializerMethodField()

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_feature_image_src(self, instance):
        """Serializes the source of the feature_image, or None if not set."""
        if hasattr(instance, "feature_image"):
            return get_wagtail_img_src(instance.feature_image) or None
        return None

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
