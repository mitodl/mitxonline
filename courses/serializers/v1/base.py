from __future__ import annotations

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from cms.serializers import CoursePageSerializer
from courses import models
from courses.constants import CONTENT_TYPE_MODEL_COURSE, CONTENT_TYPE_MODEL_PROGRAM
from courses.utils import get_approved_flexible_price_exists
from ecommerce.serializers import BaseProductSerializer, ProductFlexibilePriceSerializer
from openedx.constants import EDX_ENROLLMENT_AUDIT_MODE, EDX_ENROLLMENT_VERIFIED_MODE


class EnrollmentModeSerializer(serializers.ModelSerializer):
    """Enrollment mode serializer."""

    class Meta:
        """Meta opts for the serializer"""

        model = models.EnrollmentMode
        fields = [
            "mode_slug",
            "mode_display_name",
            "requires_payment",
        ]


class BaseCourseSerializer(serializers.ModelSerializer):
    """Basic course model serializer"""

    type = serializers.SerializerMethodField(read_only=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not self.context.get("include_page_fields") or not hasattr(instance, "page"):
            return data
        return {**data, **CoursePageSerializer(instance=instance.page).data}

    @staticmethod
    def get_type(obj) -> str:  # noqa: ARG004
        """Returns the type of object this is serializing."""
        return CONTENT_TYPE_MODEL_COURSE

    class Meta:
        model = models.Course
        fields = [
            "id",
            "title",
            "readable_id",
            "type",
        ]


class BaseCourseRunSerializer(serializers.ModelSerializer):
    """Minimal CourseRun model serializer"""

    is_archived = serializers.SerializerMethodField()
    is_upgradable = serializers.SerializerMethodField()
    is_enrollable = serializers.SerializerMethodField()
    course_number = serializers.SerializerMethodField()
    courseware_url = serializers.SerializerMethodField()
    enrollment_modes = EnrollmentModeSerializer(many=True, read_only=True)

    def get_courseware_url(self, instance) -> str | None:
        """Get the courseware URL"""
        return instance.courseware_url

    def get_is_upgradable(self, instance) -> bool:
        """Check if the course run is upgradable"""
        return instance.is_upgradable

    def get_is_enrollable(self, instance) -> bool:
        """Check if the course run is enrollable"""
        return instance.is_enrollable

    def get_is_archived(self, instance) -> bool:
        """Check if the course run is archived"""
        return instance.is_enrollable and instance.is_past

    def get_course_number(self, instance) -> str:
        """Get the course number"""
        return instance.course_number

    class Meta:
        model = models.CourseRun
        fields = [
            "title",
            "start_date",
            "end_date",
            "enrollment_start",
            "enrollment_end",
            "expiration_date",
            "courseware_url",
            "courseware_id",
            "certificate_available_date",
            "upgrade_deadline",
            "is_upgradable",
            "is_enrollable",
            "is_archived",
            "is_self_paced",
            "run_tag",
            "id",
            "live",
            "course_number",
            "enrollment_modes",
        ]


class BaseProgramSerializer(serializers.ModelSerializer):
    """Basic program model serializer"""

    type = serializers.SerializerMethodField(read_only=True)
    enrollment_modes = EnrollmentModeSerializer(many=True, read_only=True)

    @staticmethod
    def get_type(obj) -> str:  # noqa: ARG004
        return CONTENT_TYPE_MODEL_PROGRAM

    class Meta:
        model = models.Program
        fields = ["title", "readable_id", "id", "type", "enrollment_modes"]


class CourseRunCertificateSerializer(serializers.ModelSerializer):
    """CourseRunCertificate model serializer"""

    class Meta:
        model = models.CourseRunCertificate
        fields = ["uuid", "link"]


class CourseRunGradeSerializer(serializers.ModelSerializer):
    """CourseRunGrade serializer"""

    grade = serializers.FloatField(read_only=True, min_value=0.0, max_value=1.0)
    letter_grade = serializers.CharField(read_only=True, max_length=10, allow_null=True)

    class Meta:
        model = models.CourseRunGrade
        fields = ["grade", "letter_grade", "passed", "set_by_admin", "grade_percent"]
        read_only_fields = ["passed", "set_by_admin", "grade_percent"]


class BaseCourseRunEnrollmentSerializer(serializers.ModelSerializer):
    certificate = CourseRunCertificateSerializer(read_only=True, allow_null=True)
    enrollment_mode = serializers.ChoiceField(
        (EDX_ENROLLMENT_AUDIT_MODE, EDX_ENROLLMENT_VERIFIED_MODE), read_only=True
    )
    approved_flexible_price_exists = serializers.SerializerMethodField()
    grades = CourseRunGradeSerializer(many=True, read_only=True)

    @extend_schema_field(bool)
    def get_approved_flexible_price_exists(self, instance):
        return get_approved_flexible_price_exists(instance, self.context)

    class Meta:
        model = models.CourseRunEnrollment
        fields = [
            "run",
            "id",
            "edx_emails_subscription",
            "certificate",
            "enrollment_mode",
            "approved_flexible_price_exists",
            "grades",
        ]


@extend_schema_field(BaseProductSerializer)
class ProductRelatedField(serializers.RelatedField):
    """Simple serializer for the Product generic field"""

    def to_representation(self, instance):
        return BaseProductSerializer(instance=instance, context=self.context).data


@extend_schema_field(ProductFlexibilePriceSerializer)
class ProductFlexiblePriceRelatedField(serializers.RelatedField):
    """Serializer for the Product generic field, including flexible price data"""

    def to_representation(self, instance):
        return ProductFlexibilePriceSerializer(
            instance=instance, context=self.context
        ).data
