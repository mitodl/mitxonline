from django.db.models import Prefetch, Q, Count
from mitol.common.utils import now_in_utc
from rest_framework import serializers

from courses.models import CourseRun, Department


class DepartmentSerializer(serializers.ModelSerializer):
    """Department model serializer"""

    class Meta:
        model = Department
        fields = ["id", "name"]


class DepartmentWithCountSerializer(DepartmentSerializer):
    """CourseRun model serializer that includes the number of courses and programs associated with each departments"""

    courses = serializers.SerializerMethodField()
    programs = serializers.SerializerMethodField()

    def get_courses(self, instance):
        now = now_in_utc()
        related_courses = instance.course_set.filter(live=True, page__live=True)
        relevant_courseruns = CourseRun.objects.filter(
            Q(course__in=related_courses)
            & Q(live=True)
            & Q(start_date__isnull=False)
            & Q(enrollment_start__lt=now)
            & (Q(enrollment_end=None) | Q(enrollment_end__gt=now))
        ).values_list("id", flat=True)

        return (
            related_courses.filter(courseruns__id__in=relevant_courseruns)
            .distinct()
            .count()
        )

    def get_programs(self, instance):
        return (
            instance.program_set.filter(live=True, page__live=True).distinct().count()
        )

    class Meta:
        model = Department
        fields = DepartmentSerializer.Meta.fields + [
            "courses",
            "programs",
        ]
