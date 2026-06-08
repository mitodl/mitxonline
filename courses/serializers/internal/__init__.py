"""Internal-only serializers for courses."""

from rest_framework import serializers

from courses.models import Course
from courses.serializers.v2.courses import (
    CourseRunSerializer,
    CourseSerializer,
)


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

    class Meta:
        model = Course
        fields = [*CourseSerializer.Meta.fields, "courseruns"]
