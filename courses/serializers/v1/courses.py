from __future__ import annotations

from django.conf import settings
from drf_spectacular.utils import (
    extend_schema_field,
    extend_schema_serializer,
    inline_serializer,
)
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from cms.serializers import CoursePageSerializer
from courses import models
from courses.api import create_run_enrollments
from courses.serializers.v1.base import (
    BaseCourseRunEnrollmentSerializer,
    BaseCourseRunSerializer,
    BaseCourseSerializer,
    ProductFlexiblePriceRelatedField,
)
from courses.serializers.v1.departments import DepartmentSerializer
from courses.utils import get_approved_flexible_price_exists
from main import features
from openedx.constants import EDX_ENROLLMENT_AUDIT_MODE, EDX_ENROLLMENT_VERIFIED_MODE


class CourseSerializer(BaseCourseSerializer):
    """Course model serializer"""

    departments = DepartmentSerializer(many=True, read_only=True)
    next_run_id = serializers.SerializerMethodField()
    page = CoursePageSerializer(read_only=True)
    programs = serializers.SerializerMethodField()

    def get_next_run_id(self, instance) -> int | None:
        """Get next run id"""
        run = instance.first_unexpired_run
        return run.id if run is not None else None

    @extend_schema_field(
        inline_serializer(
            name="ProgramSerializer",
            fields={
                "id": serializers.IntegerField(),
                "title": serializers.CharField(),
                "readable_id": serializers.CharField(),
            },
            allow_null=True,
        )
    )
    def get_programs(self, instance):
        if self.context.get("include_programs", False):
            from courses.serializers.v1.base import (  # noqa: PLC0415
                BaseProgramSerializer,
            )

            programs = (
                models.Program.objects.select_related("page")
                .filter(pk__in=[program.id for program in instance.programs])
                .filter(live=True)
                .filter(page__live=True)
                .all()
            )

            return BaseProgramSerializer(programs, many=True).data

        return None

    class Meta:
        model = models.Course
        fields = [
            "id",
            "title",
            "readable_id",
            "next_run_id",
            "departments",
            "page",
            "programs",
        ]


@extend_schema_serializer(component_name="V1BaseCourseRun")
class CourseRunSerializer(BaseCourseRunSerializer):
    """CourseRun model serializer"""

    products = ProductFlexiblePriceRelatedField(many=True, read_only=True)
    approved_flexible_price_exists = serializers.SerializerMethodField()

    class Meta:
        model = models.CourseRun
        fields = BaseCourseRunSerializer.Meta.fields + [  # noqa: RUF005
            "products",
            "approved_flexible_price_exists",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if self.context and self.context.get("include_enrolled_flag"):
            return {
                **data,
                "is_enrolled": getattr(instance, "user_enrollments", 0) > 0,
                "is_verified": getattr(instance, "verified_enrollments", 0) > 0,
            }
        return data

    @extend_schema_field(bool)
    def get_approved_flexible_price_exists(self, instance):
        return get_approved_flexible_price_exists(instance, self.context)


@extend_schema_serializer(
    component_name="V1CourseWithCourseRunsSerializer",
)
class CourseWithCourseRunsSerializer(CourseSerializer):
    """Course model serializer - also serializes child course runs"""

    courseruns = CourseRunSerializer(many=True, read_only=True)

    class Meta:
        model = models.Course
        fields = CourseSerializer.Meta.fields + [  # noqa: RUF005
            "courseruns",
        ]


@extend_schema_serializer(component_name="V1CourseRunWithCourse")
class CourseRunWithCourseSerializer(CourseRunSerializer):
    """
    CourseRun model serializer - also serializes the parent Course.
    """

    course = CourseSerializer(read_only=True, context={"include_page_fields": True})
    courseware_url = serializers.SerializerMethodField()
    is_upgradable = serializers.SerializerMethodField()
    is_enrollable = serializers.SerializerMethodField()
    is_archived = serializers.SerializerMethodField()
    course_number = serializers.SerializerMethodField()
    products = ProductFlexiblePriceRelatedField(
        many=True,
        read_only=True,
        help_text="List of products associated with this course run",
    )

    def get_products(self, instance) -> list[dict]:
        """Get products associated with this course run"""
        return super().get_products(instance)

    class Meta:
        model = models.CourseRun
        fields = [
            *CourseRunSerializer.Meta.fields,
            "course",
            "courseware_url",
            "is_upgradable",
            "is_enrollable",
            "is_archived",
            "course_number",
            "products",
        ]


class CourseRunEnrollmentSerializer(BaseCourseRunEnrollmentSerializer):
    """CourseRunEnrollment model serializer"""

    run = CourseRunWithCourseSerializer(read_only=True)
    run_id = serializers.IntegerField(write_only=True)
    enrollment_mode = serializers.ChoiceField(
        (EDX_ENROLLMENT_AUDIT_MODE, EDX_ENROLLMENT_VERIFIED_MODE), read_only=True
    )
    approved_flexible_price_exists = serializers.SerializerMethodField()

    def create(self, validated_data):
        user = self.context["user"]
        run_id = validated_data["run_id"]
        try:
            run = models.CourseRun.objects.select_related("b2b_contract").get(id=run_id)
        except models.CourseRun.DoesNotExist:
            raise ValidationError({"run_id": f"Invalid course run id: {run_id}"})  # noqa: B904

        if run.b2b_contract is not None:
            raise ValidationError({"run_id": f"Invalid course run id: {run_id}"})
        successful_enrollments, _ = create_run_enrollments(
            user,
            [run],
            keep_failed_enrollments=settings.FEATURES.get(
                features.IGNORE_EDX_FAILURES, False
            ),
        )

        return successful_enrollments[0] if successful_enrollments else None

    class Meta(BaseCourseRunEnrollmentSerializer.Meta):
        fields = BaseCourseRunEnrollmentSerializer.Meta.fields + [  # noqa: RUF005
            "run_id",
        ]
