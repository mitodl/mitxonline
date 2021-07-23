"""CMS app serializers"""
from rest_framework import serializers

from cms import models
from cms.api import get_wagtail_img_src


class CoursePageSerializer(serializers.ModelSerializer):
    """Course page model serializer"""

    feature_image_src = serializers.SerializerMethodField()

    def get_feature_image_src(self, instance):
        """Serializes the source of the feature_image"""
        return (
            get_wagtail_img_src(instance.feature_image)
            if hasattr(instance, "feature_image")
            else None
        )

    class Meta:
        model = models.CoursePage
        fields = [
            "feature_image_src",
        ]
