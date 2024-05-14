from rest_framework import serializers

from cms.serializers import CoursePageSerializer
from courses import models
from courses.constants import CONTENT_TYPE_MODEL_COURSE, CONTENT_TYPE_MODEL_PROGRAM
from ecommerce.serializers import ProductFlexibilePriceSerializer
from flexiblepricing.api import is_courseware_flexible_price_approved
from openedx.constants import EDX_ENROLLMENT_AUDIT_MODE, EDX_ENROLLMENT_VERIFIED_MODE


class BaseCourseSerializer(serializers.ModelSerializer):
    """Basic course model serializer"""

    type = serializers.SerializerMethodField(read_only=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not self.context.get("include_page_fields") or not hasattr(instance, "page"):
            return data
        return {**data, **CoursePageSerializer(instance=instance.page).data}

    @staticmethod
    def get_type(obj):  # noqa: ARG004
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
            "is_self_paced",
            "run_tag",
            "id",
            "live",
            "course_number",
        ]


class BaseProgramSerializer(serializers.ModelSerializer):
    """Basic program model serializer"""

    type = serializers.SerializerMethodField(read_only=True)

    @staticmethod
    def get_type(obj):  # noqa: ARG004
        return CONTENT_TYPE_MODEL_PROGRAM

    class Meta:
        model = models.Program
        fields = ["title", "readable_id", "id", "type"]


class BaseCourseRunEnrollmentSerializer(serializers.ModelSerializer):
    certificate = serializers.SerializerMethodField(read_only=True)
    enrollment_mode = serializers.ChoiceField(
        (EDX_ENROLLMENT_AUDIT_MODE, EDX_ENROLLMENT_VERIFIED_MODE), read_only=True
    )
    approved_flexible_price_exists = serializers.SerializerMethodField()
    grades = serializers.SerializerMethodField(read_only=True)

    def get_certificate(self, enrollment):
        """
        Resolve a certificate for this enrollment if it exists
        """
        # When create method is called it returns list object of enrollments
        if isinstance(enrollment, list):
            enrollment = enrollment[0] if enrollment else None

        # No need to include a certificate if there is no corresponding wagtail page
        # to support the render
        try:
            if (
                not enrollment
                or not enrollment.run.course.page
                or not enrollment.run.course.page.certificate_page
            ):
                return None
        except models.Course.page.RelatedObjectDoesNotExist:
            return None

        # Using IDs because we don't need the actual record and this avoids redundant queries
        user_id = enrollment.user_id
        course_run_id = enrollment.run_id
        try:
            return CourseRunCertificateSerializer(
                models.CourseRunCertificate.objects.get(
                    user_id=user_id, course_run_id=course_run_id
                )
            ).data
        except models.CourseRunCertificate.DoesNotExist:
            return None

    def get_approved_flexible_price_exists(self, instance):
        instance_run = instance[0].run if isinstance(instance, list) else instance.run
        instance_user = (
            instance[0].user if isinstance(instance, list) else instance.user
        )
        flexible_price_exists = is_courseware_flexible_price_approved(
            instance_run, instance_user
        )
        return flexible_price_exists  # noqa: RET504

    def get_grades(self, instance):
        instance_run = instance[0].run if isinstance(instance, list) else instance.run
        instance_user = (
            instance[0].user if isinstance(instance, list) else instance.user
        )

        return CourseRunGradeSerializer(
            instance=models.CourseRunGrade.objects.filter(
                user=instance_user, course_run=instance_run
            ).all(),
            many=True,
        ).data

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


class ProductRelatedField(serializers.RelatedField):
    """serializer for the Product generic field"""

    def to_representation(self, instance):
        serializer = ProductFlexibilePriceSerializer(
            instance=instance, context=self.context
        )
        return serializer.data


class CourseRunCertificateSerializer(serializers.ModelSerializer):
    """CourseRunCertificate model serializer"""

    class Meta:
        model = models.CourseRunCertificate
        fields = ["uuid", "link"]


class CourseRunGradeSerializer(serializers.ModelSerializer):
    """CourseRunGrade serializer"""

    class Meta:
        model = models.CourseRunGrade
        fields = ["grade", "letter_grade", "passed", "set_by_admin", "grade_percent"]
