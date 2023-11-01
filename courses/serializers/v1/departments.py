from rest_framework import serializers

from courses import models


class DepartmentSerializer(serializers.ModelSerializer):
    """Department model serializer"""

    class Meta:
        model = models.Department
        fields = ["name", "id"]


class DepartmentWithCountSerializer(DepartmentSerializer):
    """CourseRun model serializer that includes the number of courses and programs associated with each departments"""

    courses = serializers.IntegerField()
    programs = serializers.IntegerField()

    class Meta:
        model = models.Department
        fields = DepartmentSerializer.Meta.fields + [
            "courses",
            "programs",
        ]
