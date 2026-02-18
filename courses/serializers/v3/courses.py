"""Courses v3 serializers"""

from __future__ import annotations

import logging

from django.conf import settings
from drf_spectacular.utils import extend_schema_field, extend_schema_serializer
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from courses import models
from courses.api import create_run_enrollments
from courses.serializers.v1.base import (
    BaseCourseRunEnrollmentSerializer,
    BaseCourseRunSerializer,
    BaseCourseSerializer,
)
from courses.serializers.v3.certificates import CourseRunCertificateSerializer
from main import features

log = logging.getLogger(__name__)


@extend_schema_serializer(component_name="CourseV3")
class CourseSerializer(BaseCourseSerializer):
    """Course serializer"""


@extend_schema_serializer(component_name="CourseRunWithCourseV3")
class CourseRunWithCourseSerializer(BaseCourseRunSerializer):
    """CourseRun serializer"""

    course = CourseSerializer(read_only=True)

    class Meta(BaseCourseRunSerializer.Meta):
        fields = [
            *BaseCourseRunSerializer.Meta.fields,
            "course",
        ]


@extend_schema_serializer(component_name="CourseRunEnrollmentV3")
class CourseRunEnrollmentSerializer(BaseCourseRunEnrollmentSerializer):
    """CourseRunEnrollment model serializer"""

    run = CourseRunWithCourseSerializer(read_only=True)
    run_id = serializers.IntegerField(write_only=True)
    certificate = CourseRunCertificateSerializer(read_only=True, allow_null=True)

    b2b_organization_id = serializers.SerializerMethodField(read_only=True)
    b2b_contract_id = serializers.SerializerMethodField(read_only=True)

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_b2b_organization_id(self, enrollment):
        """Get the B2B organization ID if this enrollment is associated with a B2B contract."""
        if enrollment.run.b2b_contract:
            return enrollment.run.b2b_contract.organization_id
        return None

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_b2b_contract_id(self, enrollment):
        """Get the B2B contract ID if this enrollment is associated with a B2B contract."""
        return enrollment.run.b2b_contract_id

    def create(self, validated_data):
        """Create a new course run enrollment."""
        user = self.context["user"]
        run_id = validated_data["run_id"]
        run = models.CourseRun.objects.filter(id=run_id).first()

        if run is None or run.b2b_contract_id is not None:
            raise ValidationError({"run_id": f"Invalid course run id: {run_id}"})

        successful_enrollments, _ = create_run_enrollments(
            user,
            [run],
            keep_failed_enrollments=settings.FEATURES.get(
                features.IGNORE_EDX_FAILURES, False
            ),
        )
        return successful_enrollments

    class Meta(BaseCourseRunEnrollmentSerializer.Meta):
        model = models.CourseRunEnrollment
        fields = [
            *BaseCourseRunEnrollmentSerializer.Meta.fields,
            "run",
            "run_id",
            "b2b_organization_id",
            "b2b_contract_id",
            "certificate",
        ]
