"""CMS app serializers"""
import bleach
from django.contrib.contenttypes.models import ContentType
from django.templatetags.static import static
from rest_framework import serializers

from cms import models
from cms.api import get_wagtail_img_src
from cms.models import FlexiblePricingRequestForm, ProgramPage
from courses.constants import DEFAULT_COURSE_IMG_PATH
from ecommerce.models import Product


class CoursePageSerializer(serializers.ModelSerializer):
    """Course page model serializer"""

    feature_image_src = serializers.SerializerMethodField()
    page_url = serializers.SerializerMethodField()
    financial_assistance_form_url = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    current_price = serializers.SerializerMethodField()
    instructors = serializers.SerializerMethodField()
    live = serializers.SerializerMethodField()

    def get_feature_image_src(self, instance):
        """Serializes the source of the feature_image"""
        feature_img_src = None
        if hasattr(instance, "feature_image"):
            feature_img_src = get_wagtail_img_src(instance.feature_image)

        return feature_img_src or static(DEFAULT_COURSE_IMG_PATH)

    def get_page_url(self, instance):
        return instance.get_url()

    def get_financial_assistance_form_url(self, instance):
        """
        Returns URL of the Financial Assistance Form.
        """
        financial_assistance_page = None
        related_program_requirements = instance.product.in_programs.filter(program__live=True)
        for program_requirement in related_program_requirements:

            program = program_requirement.program

            program_page = ProgramPage.objects.filter(
                program_id=program
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

            if financial_assistance_page is None:
                financial_assistance_page = FlexiblePricingRequestForm.objects.filter(
                    selected_program=program
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

    def get_next_run_id(self, instance):
        """Get next run id"""
        run = instance.course.first_unexpired_run
        return run.id if run is not None else None

    def get_description(self, instance):
        return bleach.clean(instance.description, tags=[], strip=True)

    def get_current_price(self, instance):
        next_run = self.get_next_run_id(instance)

        if next_run is None:
            return None

        course_ct = ContentType.objects.get(app_label="courses", model="courserun")

        relevant_product = (
            Product.objects.filter(
                content_type=course_ct, object_id=next_run, is_active=True
            )
            .order_by("-price")
            .first()
        )
        return relevant_product.price if relevant_product else None

    def get_instructors(self, instance):
        members = [member.value for member in instance.faculty_members]
        returnable_members = []

        for member in members:
            returnable_members.append(
                {
                    "name": member["name"],
                    "description": bleach.clean(
                        member["description"].source, tags=[], strip=True
                    ),
                }
            )

        return returnable_members

    def get_live(self, instance):
        return instance.live

    class Meta:
        model = models.CoursePage
        fields = [
            "feature_image_src",
            "page_url",
            "financial_assistance_form_url",
            "description",
            "current_price",
            "instructors",
            "live",
        ]
