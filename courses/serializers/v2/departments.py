from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from courses.models import Department


class DepartmentSerializer(serializers.ModelSerializer):
    """Department model serializer"""

    class Meta:
        model = Department
        fields = ["id", "name", "slug"]


class DepartmentWithCoursesAndProgramsSerializer(DepartmentSerializer):
    """Department model serializer that includes the number of courses and programs associated with each"""

    course_ids = serializers.SerializerMethodField()
    program_ids = serializers.SerializerMethodField()

    @extend_schema_field(serializers.ListField(child=serializers.IntegerField()))
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
        return [course.id for course in instance.courses.all()]

    @extend_schema_field(serializers.ListField(child=serializers.IntegerField()))
    def get_program_ids(self, instance):
        """
        Returns a list of program IDs associated with the department
        if the program is live and has a live CMS page.

        Args:
            instance (courses.models.Department): Department model instance.

        Returns:
            list: Program IDs associated with the Department.
        """
        return [program.id for program in instance.programs.all()]

    class Meta:
        model = Department
        fields = DepartmentSerializer.Meta.fields + [  # noqa: RUF005
            "course_ids",
            "program_ids",
        ]
