"""Internal-only serializers for courses."""

from rest_framework import serializers

from courses.models import Course
from courses.serializers.v2.courses import (
    CourseRunSerializer,
    CourseSerializer,
)
from courses.utils import get_dated_courseruns


class IngestibleCourseWithCourseRunsSerializer(CourseSerializer):
    """Course model serializer - also serializes child course runs"""

    courseruns = serializers.SerializerMethodField()

    def _get_courseruns(self, instance):
        """Return either the prefetched courseruns or use the FK directly."""

        return getattr(instance, "prefetched_courseruns", instance.courseruns)

    def get_courseruns(self, instance):
        """Get courseruns. This should be all of them."""

        return CourseRunSerializer(
            self._get_courseruns(instance),
            many=True,
            read_only=True,
            context=self.context,
        ).data

    def get_availability(self, instance):
        """Get course availability"""
        dated_courseruns = getattr(
            instance,
            "prefetched_dated_courseruns",
            get_dated_courseruns(instance.courseruns),
        )
        if len(dated_courseruns) == 0:
            return "anytime"
        return "dated"

    class Meta:
        model = Course
        fields = [*CourseSerializer.Meta.fields, "courseruns"]
