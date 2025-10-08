from rest_framework import serializers

from courses import models


class DepartmentSerializer(serializers.ModelSerializer):
    """Department model serializer"""

    class Meta:
        model = models.Department
        fields = ["name"]


class DepartmentWithCountSerializer(DepartmentSerializer):
    """CourseRun model serializer that includes the number of courses and programs associated with each departments"""

    courses = serializers.IntegerField(source="courses_count")
    programs = serializers.IntegerField(source="program_count")

    class Meta:
        model = models.Department
        fields = DepartmentSerializer.Meta.fields + [  # noqa: RUF005
            "courses",
            "programs",
        ]
