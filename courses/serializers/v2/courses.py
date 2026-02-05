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
from courses.serializers.utils import get_topics_from_page
from courses.serializers.v1.base import (
    BaseCourseRunEnrollmentSerializer,
    BaseCourseRunSerializer,
    BaseCourseSerializer,
    BaseProgramSerializer,
    ProductRelatedField,
)
from courses.serializers.v1.departments import DepartmentSerializer
from courses.utils import get_approved_flexible_price_exists, get_dated_courseruns
from main import features
from openedx.constants import EDX_ENROLLMENT_AUDIT_MODE, EDX_ENROLLMENT_VERIFIED_MODE

log = logging.getLogger(__name__)


@extend_schema_serializer(component_name="V2Course")
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
    min_price = serializers.SerializerMethodField()
    max_price = serializers.SerializerMethodField()
    include_in_learn_catalog = serializers.BooleanField(read_only=True)
    ingest_content_files_for_ai = serializers.BooleanField(read_only=True)

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

    @extend_schema_field(BaseProgramSerializer(many=True, allow_null=True))
    def get_programs(self, instance):
        """
        Include appropriate programs.

        If the org or contract ID is set, include only programs that match. If
        neither is specified, filter programs that have "b2b_only" set.
        """
        if self.context.get("include_programs", False):
            programs_qs = instance.in_programs

            if self.context.get("org_id"):
                programs_qs = programs_qs.filter(
                    program__contract_memberships__contract__organization__pk=self.context.get(
                        "org_id"
                    )
                )
            elif self.context.get("contract_id"):
                programs_qs = programs_qs.filter(
                    program__contract_memberships__contract__pk=self.context.get(
                        "contract_id"
                    )
                )
            else:
                programs_qs = programs_qs.filter(program__b2b_only=False)

            programs = [
                req.program for req in programs_qs.prefetch_related("program").all()
            ]

            return BaseProgramSerializer(programs, many=True).data

        return None

    @extend_schema_field(list[dict])
    def get_topics(self, instance):
        """List topics of a course"""
        if hasattr(instance, "page") and instance.page is not None:
            return get_topics_from_page(instance.page)
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

    def get_min_price(self, instance) -> int | None:
        """
        Get the min price of the product from the CMS page.
        """
        if hasattr(instance, "page") and hasattr(instance.page, "min_price"):
            return instance.page.min_price
        return None

    def get_max_price(self, instance) -> int | None:
        """
        Get the max price of the product from the CMS page.
        """
        if hasattr(instance, "page") and hasattr(instance.page, "max_price"):
            return instance.page.max_price
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
            "min_price",
            "max_price",
            "time_commitment",
            "availability",
            "min_weekly_hours",
            "max_weekly_hours",
            "include_in_learn_catalog",
            "ingest_content_files_for_ai",
        ]


@extend_schema_serializer(component_name="CourseRunV2")
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
        return get_approved_flexible_price_exists(instance, self.context)


@extend_schema_serializer(component_name="CourseWithCourseRunsSerializerV2")
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
        if "contract_id" in self.context:
            courseruns = courseruns.filter(b2b_contract_id=self.context["contract_id"])

        return CourseRunSerializer(courseruns, many=True, read_only=True).data

    class Meta:
        model = models.Course
        fields = [*CourseSerializer.Meta.fields, "courseruns"]


@extend_schema_serializer(component_name="V2CourseRunWithCourse")
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


@extend_schema_serializer(component_name="CourseRunEnrollmentRequestV2")
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
    b2b_organization_id = serializers.SerializerMethodField()
    b2b_contract_id = serializers.SerializerMethodField()

    def create(self, validated_data):
        """Create a new course run enrollment."""
        user = self.context["user"]
        run_id = validated_data["run_id"]
        try:
            run = models.CourseRun.objects.get(id=run_id)
        except models.CourseRun.DoesNotExist:
            raise ValidationError({"run_id": f"Invalid course run id: {run_id}"})  # noqa: B904
        successful_enrollments, _ = create_run_enrollments(
            user,
            [run],
            keep_failed_enrollments=is_enabled(features.IGNORE_EDX_FAILURES),
        )
        return successful_enrollments

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_b2b_organization_id(self, enrollment):
        """Get the B2B organization ID if this enrollment is associated with a B2B contract."""
        if enrollment.run.b2b_contract:
            return enrollment.run.b2b_contract.organization.id
        return None

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_b2b_contract_id(self, enrollment):
        """Get the B2B contract ID if this enrollment is associated with a B2B contract."""
        if enrollment.run.b2b_contract:
            return enrollment.run.b2b_contract.id
        return None

    class Meta(BaseCourseRunEnrollmentSerializer.Meta):
        fields = BaseCourseRunEnrollmentSerializer.Meta.fields + [  # noqa: RUF005
            "run_id",
            "b2b_organization_id",
            "b2b_contract_id",
        ]


class CourseTopicSerializer(serializers.ModelSerializer):
    """
    CoursesTopic model serializer
    """

    class Meta:
        model = models.CoursesTopic
        fields = ["name", "parent"]
