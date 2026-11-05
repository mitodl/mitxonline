"""Internal-only serializers for courses."""

from courses.models import Course
from courses.serializers.v2.courses import (
    CourseRunSerializer,
    CourseSerializer,
)
from courses.utils import get_dated_courseruns


class IngestibleCourseWithCourseRunsSerializer(CourseSerializer):
    """Course model serializer - also serializes child course runs"""

    courseruns = CourseRunSerializer(many=True, read_only=True)

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
