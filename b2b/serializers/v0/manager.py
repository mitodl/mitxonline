"""B2B manager dashboard serializers."""

from rest_framework import serializers

from b2b.models import ContractPage
from b2b.serializers.v0 import ContractPageSerializer
from courses.models import CourseRun, CourseRunEnrollment
from ecommerce.models import Discount


class ManagerContractDetailSerializer(ContractPageSerializer):
    """Serializer for detailed contract view with statistics."""

    attachment_percentage = serializers.SerializerMethodField()
    total_enrollments = serializers.SerializerMethodField()
    total_codes = serializers.SerializerMethodField()

    class Meta:
        model = ContractPage
        fields = [
            *ContractPageSerializer.Meta.fields,
            "attachment_percentage",
            "total_enrollments",
            "total_codes",
        ]
        read_only_fields = [
            *ContractPageSerializer.Meta.read_only_fields,
            "attachment_percentage",
            "total_enrollments",
            "total_codes",
        ]

    def get_attachment_percentage(self, obj) -> float | None:
        """Calculate attachment percentage if seat-limited."""
        if not obj.max_learners:
            return None

        attached_count = obj.get_learners().count()
        return round((attached_count / obj.max_learners) * 100, 2)

    def get_total_enrollments(self, obj) -> int:
        """Get total number of enrollments across all contract course runs."""
        return CourseRunEnrollment.objects.filter(run__b2b_contract=obj).count()

    def get_total_codes(self, obj) -> int:
        """Get total number of discount codes for this contract."""
        return obj.get_discounts().count()


class ManagerCourseRunSerializer(serializers.ModelSerializer):
    """Serializer for course runs in a contract."""

    class Meta:
        model = CourseRun
        fields = [
            "readable_id",
            "title",
            "start_date",
            "end_date",
            "enrollment_start",
            "enrollment_end",
            "certificate_available_date",
            "live",
        ]


class ManagerEnrollmentSerializer(serializers.ModelSerializer):
    """Serializer for enrollments in a specific course run."""

    learner_name = serializers.CharField(source="user.name")
    learner_email = serializers.CharField(source="user.email")
    enrollment_date = serializers.DateTimeField(source="created_on")
    enrollment_type = serializers.CharField(source="enrollment_mode")
    enrollment_status = serializers.CharField(source="change_status")

    class Meta:
        model = CourseRunEnrollment
        fields = [
            "learner_name",
            "learner_email",
            "enrollment_date",
            "enrollment_type",
            "enrollment_status",
            "active",
        ]


class ManagerEnrollmentCodeSerializer(serializers.ModelSerializer):
    """Serializer for enrollment codes available to a contract."""

    code = serializers.CharField(source="discount_code")
    is_redeemed = serializers.SerializerMethodField()
    redeemed_by = serializers.SerializerMethodField()
    redeemed_on = serializers.SerializerMethodField()

    class Meta:
        model = Discount
        fields = ["id", "code", "is_redeemed", "redeemed_by", "redeemed_on"]

    def get_is_redeemed(self, obj) -> bool:
        """Check if this code has been used for contract attachment."""
        contract = self.context.get("contract")
        if not contract:
            return False

        return obj.contract_redemptions.exists()

    def get_redeemed_by(self, obj) -> str | None:
        """Return the user that redeemed the code (last)."""

        contract = self.context.get("contract")
        if not contract:
            return None

        last_redemption = obj.contract_redemptions.last()

        return last_redemption.user.email if last_redemption else None

    def get_redeemed_on(self, obj) -> str | None:
        """Return the date that the code was redeemed on last."""

        contract = self.context.get("contract")
        if not contract:
            return None

        last_redemption = obj.contract_redemptions.last()

        return str(last_redemption.created_on) if last_redemption else None
