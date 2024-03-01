from django.db.models import Q
from mitol.common.utils import now_in_utc
from rest_framework import serializers

from courses.models import CourseRun, Department


class DepartmentSerializer(serializers.ModelSerializer):
    """Department model serializer"""

    class Meta:
        model = Department
        fields = ["id", "name"]


class DepartmentWithCoursesAndProgramsSerializer(DepartmentSerializer):
    """Department model serializer that includes the number of courses and programs associated with each"""

    course_ids = serializers.SerializerMethodField()
    program_ids = serializers.SerializerMethodField()

    def get_course_ids(self, instance):
        """
        Returns a list of course IDs associated with courses which are live and
        have a CMS page that is live.  The associated course runs must be live,
        have a start date, enrollment start date in the past, and enrollment end
        date in the future or not defined.

        Args:
            instance (courses.models.Department): Department model instance.

        Returns:
            list: Course IDs associated with the Department.
        """
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
            .values_list("id", flat=True)
        )

    def get_program_ids(self, instance):
        """
        Returns a list of program IDs associated with the department
        if the program is live and has a live CMS page.

        Args:
            instance (courses.models.Department): Department model instance.

        Returns:
            list: Program IDs associated with the Department.
        """
        return (
            instance.program_set.filter(live=True, page__live=True)
            .distinct()
            .values_list("id", flat=True)
        )

    class Meta:
        model = Department
        fields = DepartmentSerializer.Meta.fields + [
            "course_ids",
            "program_ids",
        ]
