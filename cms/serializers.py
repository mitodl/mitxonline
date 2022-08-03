"""CMS app serializers"""
from django.templatetags.static import static
from rest_framework import serializers

from cms import models
from cms.api import get_wagtail_img_src
from cms.models import FlexiblePricingRequestForm
from courses.constants import DEFAULT_COURSE_IMG_PATH


class CoursePageSerializer(serializers.ModelSerializer):
    """Course page model serializer"""

    feature_image_src = serializers.SerializerMethodField()
    page_url = serializers.SerializerMethodField()
    financial_assistance_form_url = serializers.SerializerMethodField()

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
        financial_assistance_page = (
            instance.get_children().type(FlexiblePricingRequestForm).live().first()
        )
        return (
            f"{instance.get_url()}{financial_assistance_page.slug}/"
            if financial_assistance_page
            else ""
        )

    class Meta:
        model = models.CoursePage
        fields = [
            "feature_image_src",
            "page_url",
            "financial_assistance_form_url",
        ]
