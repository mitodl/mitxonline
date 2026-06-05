"""B2B manager dashboard serializers."""

from datetime import datetime

from rest_framework import serializers

from b2b.models import REDEMPTION_STATUS_UNASSIGNED, ContractPage
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

        attached_count = obj.users.count()
        return round((attached_count / obj.max_learners) * 100, 2)

    def get_total_enrollments(self, obj) -> int:
        """Get total number of enrollments across all contract course runs."""
        return obj.enrollment_count

    def get_total_codes(self, obj) -> int:
        """Get total number of discount codes for this contract."""
        return obj.discount_count


class ManagerCourseRunSerializer(serializers.ModelSerializer):
    """Serializer for course runs in a contract."""

    readable_id = serializers.CharField(read_only=True)

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


class AssignRevokeCodeSerializer(serializers.Serializer):
    """Serializer for the assign_code request body."""

    email = serializers.EmailField()
    name = serializers.CharField(max_length=255, default="", allow_blank=True)


class ManagerEnrollmentCodeSerializer(serializers.ModelSerializer):
    """Serializer for enrollment codes available to a contract."""

    code = serializers.CharField(source="discount_code")
    redemption_status = serializers.SerializerMethodField()
    assigned_to = serializers.SerializerMethodField()
    assigned_on = serializers.SerializerMethodField()
    assigned_name = serializers.SerializerMethodField()
    redeemed_on = serializers.SerializerMethodField()
    redeemed_by = serializers.SerializerMethodField()
    last_sent = serializers.SerializerMethodField()

    class Meta:
        model = Discount
        fields = [
            "id",
            "code",
            "redemption_status",
            "assigned_to",
            "assigned_on",
            "assigned_name",
            "redeemed_on",
            "redeemed_by",
            "last_sent",
        ]

    def _get_redemption(self, obj):
        """
        Return the most recent DiscountContractAttachmentRedemption
        For contracts where max_learners is set, we should only ever have 0 or 1 redemption per code.
        """
        redemptions = getattr(obj, "prefetched_redemptions", None)
        return redemptions[0] if redemptions else None

    def get_redemption_status(self, obj) -> str:
        """
        Return the redemption status of this code.

        - "unassigned": no DiscountContractAttachmentRedemption record exists
        - "assigned": a record exists but the code has not been claimed yet
        - "redeemed": the code has been claimed
        """
        redemption = self._get_redemption(obj)
        return redemption.status if redemption else REDEMPTION_STATUS_UNASSIGNED

    def get_assigned_to(self, obj) -> str | None:
        """Return the email address this code is assigned to."""
        redemption = self._get_redemption(obj)
        if not redemption:
            return None
        return redemption.assigned_email

    def get_assigned_on(self, obj) -> datetime | None:
        """Return when the invite/assignment was created."""
        redemption = self._get_redemption(obj)
        return redemption.created_on if redemption else None

    def get_redeemed_on(self, obj) -> datetime | None:
        """Return when the code was actually claimed."""
        redemption = self._get_redemption(obj)
        return redemption.redeemed_on if redemption else None

    def get_redeemed_by(self, obj) -> str | None:
        """Return the email address of the user who redeemed this code."""
        redemption = self._get_redemption(obj)
        if not redemption or not redemption.user:
            return None
        return redemption.user.email

    def get_assigned_name(self, obj) -> str | None:
        """Return the name of the user this code is assigned to."""
        redemption = self._get_redemption(obj)
        if not redemption:
            return None
        return redemption.assigned_name

    def get_last_sent(self, obj) -> datetime | None:
        """Return when the last reminder email was sent."""
        redemption = self._get_redemption(obj)
        return redemption.last_reminder_sent_on if redemption else None
