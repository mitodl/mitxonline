"""Courses v3 serializers"""

from __future__ import annotations

import logging

from drf_spectacular.utils import extend_schema_field, extend_schema_serializer
from rest_framework import serializers

from courses import models
from courses.serializers.v1.base import (
    BaseCourseRunSerializer,
    BaseCourseSerializer,
    CourseRunGradeSerializer,
)
from courses.serializers.v3.certificates import CourseRunCertificateSerializer
from openedx.constants import EDX_ENROLLMENT_AUDIT_MODE, EDX_ENROLLMENT_VERIFIED_MODE

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
class CourseRunEnrollmentSerializer(serializers.ModelSerializer):
    """CourseRunEnrollment model serializer"""

    run = CourseRunWithCourseSerializer(read_only=True)
    enrollment_mode = serializers.ChoiceField(
        (EDX_ENROLLMENT_AUDIT_MODE, EDX_ENROLLMENT_VERIFIED_MODE), read_only=True
    )
    certificate = CourseRunCertificateSerializer(read_only=True, allow_null=True)
    grades = CourseRunGradeSerializer(many=True, read_only=True)

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

    class Meta:
        model = models.CourseRunEnrollment
        fields = [
            "id",
            "run",
            "b2b_organization_id",
            "b2b_contract_id",
            "enrollment_mode",
            "certificate",
            "grades",
        ]
