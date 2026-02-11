"""Courses v2 serializers"""

from __future__ import annotations

import logging

from django.conf import settings
from drf_spectacular.utils import extend_schema_field, extend_schema_serializer
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from courses import models
from courses.api import create_run_enrollments
from main import features
from openedx.constants import EDX_ENROLLMENT_AUDIT_MODE, EDX_ENROLLMENT_VERIFIED_MODE

log = logging.getLogger(__name__)


@extend_schema_serializer(component_name="CourseRunEnrollmentV3")
class CourseRunEnrollmentSerializer(serializers.ModelSerializer):
    """CourseRunEnrollment model serializer"""

    run_id = serializers.IntegerField(write_only=True)
    enrollment_mode = serializers.ChoiceField(
        (EDX_ENROLLMENT_AUDIT_MODE, EDX_ENROLLMENT_VERIFIED_MODE), read_only=True
    )
    certificate = CourseRunCertificateSerializer(read_only=True, allow_null=True)
    grades = CourseRunGradeSerializer(many=True, read_only=True)

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
            keep_failed_enrollments=settings.FEATURES.get(
                features.IGNORE_EDX_FAILURES, False
            ),
        )
        return successful_enrollments[0]

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_b2b_organization_id(self, enrollment):
        """Get the B2B organization ID if this enrollment is associated with a B2B contract."""
        if enrollment.run.b2b_contract:
            return enrollment.run.b2b_contract.organization_id
        return None

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_b2b_contract_id(self, enrollment):
        """Get the B2B contract ID if this enrollment is associated with a B2B contract."""
        return enrollment.run.b2b_contract_id:

    class Meta:
        fields = [
            "id",
            "run_id",
            "b2b_organization_id",
            "b2b_contract_id",
            "enrollment_mode",
            "edx_emails_subscription",
            "certificate",
            "grades",
        ]
