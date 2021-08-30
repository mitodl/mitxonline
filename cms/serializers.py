"""CMS app serializers"""
from rest_framework import serializers

from cms import models
from cms.api import get_wagtail_img_src
from courses.constants import DEFAULT_COURSE_IMG_PATH
from django.templatetags.static import static

class CoursePageSerializer(serializers.ModelSerializer):
    """Course page model serializer"""

    feature_image_src = serializers.SerializerMethodField()

    def get_feature_image_src(self, instance):
        """Serializes the source of the feature_image"""
        feature_img_src = None
        if hasattr(instance, "feature_image"):
            feature_img_src = get_wagtail_img_src(instance.feature_image)        
        
        return feature_img_src if feature_img_src else static(DEFAULT_COURSE_IMG_PATH)

    class Meta:
        model = models.CoursePage
        fields = [
            "feature_image_src",
        ]
