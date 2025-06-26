"""Courses v2 serializers"""

from __future__ import annotations

import logging

from drf_spectacular.utils import extend_schema_field, extend_schema_serializer
from mitol.olposthog.features import is_enabled
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from cms.serializers import CoursePageSerializer
from courses import models
from courses.api import create_run_enrollments
from courses.models import CoursesTopic
from courses.serializers.v1.base import (
    BaseCourseRunEnrollmentSerializer,
    BaseCourseRunSerializer,
    BaseCourseSerializer,
    ProductRelatedField,
)
from courses.serializers.v1.departments import DepartmentSerializer
from courses.utils import get_dated_courseruns
from flexiblepricing.api import is_courseware_flexible_price_approved
from main import features
from openedx.constants import EDX_ENROLLMENT_AUDIT_MODE, EDX_ENROLLMENT_VERIFIED_MODE

log = logging.getLogger(__name__)


class CourseSerializer(BaseCourseSerializer):
    """Course model serializer"""

    departments = DepartmentSerializer(many=True, read_only=True)
    next_run_id = serializers.SerializerMethodField()
    page = CoursePageSerializer(read_only=True)
    programs = serializers.SerializerMethodField()
    topics = serializers.SerializerMethodField()
    certificate_type = serializers.SerializerMethodField()
    availability = serializers.SerializerMethodField()
    required_prerequisites = serializers.SerializerMethodField()
    duration = serializers.SerializerMethodField()
    min_weeks = serializers.SerializerMethodField()
    max_weeks = serializers.SerializerMethodField()
    time_commitment = serializers.SerializerMethodField()
    min_weekly_hours = serializers.SerializerMethodField()
    max_weekly_hours = serializers.SerializerMethodField()

    @extend_schema_field(bool)
    def get_required_prerequisites(self, instance):
        """
        Check if the prerequisites field is populated in the course page CMS.
        Returns:
            bool: True when the prerequisites field is populated in the course page CMS.  False otherwise.
        """
        return bool(
            hasattr(instance, "page")
            and hasattr(instance.page, "prerequisites")
            and instance.page.prerequisites != ""
        )

    @extend_schema_field(str)
    def get_duration(self, instance):
        """
        Get the duration of the course from the course page CMS.
        """
        if hasattr(instance, "page") and hasattr(instance.page, "length"):
            return instance.page.length

        return None

    def get_time_commitment(self, instance) -> str | None:
        """
        Get the time commitment of the course from the course page CMS.
        """
        if hasattr(instance, "page") and hasattr(instance.page, "effort"):
            return instance.page.effort

        return None

    def get_min_weekly_hours(self, instance) -> str | None:
        """
        Get the min weekly hours of the course from the course page CMS.
        """
        if hasattr(instance, "page") and hasattr(instance.page, "min_weekly_hours"):
            return instance.page.min_weekly_hours

        return None

    def get_max_weekly_hours(self, instance) -> str | None:
        """
        Get the max weekly hours of the course from the course page CMS.
        """
        if hasattr(instance, "page") and hasattr(instance.page, "max_weekly_hours"):
            return instance.page.max_weekly_hours

        return None

    def get_next_run_id(self, instance) -> int | None:
        """Get next run id"""
        if self.context.get("org_id"):
            run = instance.get_first_unexpired_org_run(
                self.context.get("user_contracts")
            )
        else:
            run = instance.first_unexpired_run
        return run.id if run is not None else None

    def get_programs(self, instance) -> list[dict] | None:
        if self.context.get("all_runs", False):
            from courses.serializers.v1.base import BaseProgramSerializer

            return BaseProgramSerializer(instance.programs, many=True).data

        return None

    @extend_schema_field(list[dict])
    def get_topics(self, instance):
        """List topics of a course"""
        if hasattr(instance, "page") and instance.page is not None:
            course_topics = instance.page.topics.all()
            parent_topics = CoursesTopic.objects.filter(
                child_topics__in=course_topics
            ).distinct()
            all_topics = sorted(
                [{"name": topic.name} for topic in course_topics],
                key=lambda topic: topic["name"],
            )

            for parent_topic in parent_topics:
                all_topics.append({"name": parent_topic.name})
            return all_topics
        return []

    @extend_schema_field(str)
    def get_certificate_type(self, instance):
        if instance.programs:
            program = instance.programs[0]
            if "MicroMasters" in program.program_type:
                return "MicroMasters Credential"
        return "Certificate of Completion"

    @extend_schema_field(str)
    def get_availability(self, instance):
        """Get course availability"""
        dated_courseruns = get_dated_courseruns(instance.courseruns)
        if dated_courseruns.count() == 0:
            return "anytime"
        return "dated"

    def get_min_weeks(self, instance) -> int | None:
        """
        Get the min weeks of the course from the CMS page.
        """
        if hasattr(instance, "page") and hasattr(instance.page, "min_weeks"):
            return instance.page.min_weeks

        return None

    def get_max_weeks(self, instance) -> int | None:
        """
        Get the max weeks of the course from the CMS page.
        """
        if hasattr(instance, "page") and hasattr(instance.page, "max_weeks"):
            return instance.page.max_weeks

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
            "topics",
            "certificate_type",
            "required_prerequisites",
            "duration",
            "min_weeks",
            "max_weeks",
            "time_commitment",
            "availability",
            "min_weekly_hours",
            "max_weekly_hours",
        ]


@extend_schema_serializer(
    component_name="V2CourseRunSerializer",
)
class CourseRunSerializer(BaseCourseRunSerializer):
    """CourseRun model serializer"""

    products = ProductRelatedField(many=True, read_only=True)
    approved_flexible_price_exists = serializers.SerializerMethodField()

    class Meta:
        model = models.CourseRun
        fields = BaseCourseRunSerializer.Meta.fields + [  # noqa: RUF005
            "products",
            "approved_flexible_price_exists",
            "b2b_contract",
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
        if not self.context or not self.context.get("include_approved_financial_aid"):
            return False

        # Get the User object if it exists.
        user = self.context["request"].user if "request" in self.context else None

        # Check for an approved flexible price record if the
        # user exists and has an ID (not an Anonymous user).
        # Otherwise return False.
        flexible_price_exists = (
            is_courseware_flexible_price_approved(
                instance.course, self.context["request"].user
            )
            if user and user.id
            else False
        )
        return flexible_price_exists  # noqa: RET504


class CourseWithCourseRunsSerializer(CourseSerializer):
    """Course model serializer - also serializes child course runs"""

    courseruns = serializers.SerializerMethodField()

    @extend_schema_field(CourseRunSerializer(many=True))
    def get_courseruns(self, instance):
        """Get the course runs for the given instance."""
        courseruns = instance.courseruns.order_by("id")

        if "org_id" in self.context:
            courseruns = courseruns.filter(
                b2b_contract__organization_id=self.context["org_id"]
            )

        return CourseRunSerializer(courseruns, many=True, read_only=True).data

    class Meta:
        model = models.Course
        fields = [*CourseSerializer.Meta.fields, "courseruns"]


class CourseRunWithCourseSerializer(CourseRunSerializer):
    """
    CourseRun model serializer - also serializes the parent Course.
    """

    course = CourseSerializer(read_only=True, context={"include_page_fields": True})

    class Meta:
        model = models.CourseRun
        fields = CourseRunSerializer.Meta.fields + [  # noqa: RUF005
            "course",
        ]


class CourseRunEnrollmentSerializer(BaseCourseRunEnrollmentSerializer):
    """CourseRunEnrollment model serializer"""

    run = CourseRunWithCourseSerializer(read_only=True)
    run_id = serializers.IntegerField(write_only=True)
    certificate = serializers.SerializerMethodField(read_only=True)
    enrollment_mode = serializers.ChoiceField(
        (EDX_ENROLLMENT_AUDIT_MODE, EDX_ENROLLMENT_VERIFIED_MODE), read_only=True
    )
    approved_flexible_price_exists = serializers.SerializerMethodField()
    grades = serializers.SerializerMethodField(read_only=True)

    def create(self, validated_data):
        user = self.context["user"]
        run_id = validated_data["run_id"]
        try:
            run = models.CourseRun.objects.get(id=run_id)
        except models.CourseRun.DoesNotExist:
            raise ValidationError({"run_id": f"Invalid course run id: {run_id}"})  # noqa: B904
        successful_enrollments, edx_request_success = create_run_enrollments(
            user,
            [run],
            keep_failed_enrollments=is_enabled(features.IGNORE_EDX_FAILURES),
        )
        return successful_enrollments

    class Meta(BaseCourseRunEnrollmentSerializer.Meta):
        fields = BaseCourseRunEnrollmentSerializer.Meta.fields + [  # noqa: RUF005
            "run_id",
        ]


class CourseTopicSerializer(serializers.ModelSerializer):
    """
    CoursesTopic model serializer
    """

    class Meta:
        model = models.CoursesTopic
        fields = ["name", "parent"]
