"""B2B manager dashboard serializers."""

from rest_framework import serializers

from b2b.models import ContractPage, DiscountContractAttachmentRedemption
from courses.models import CourseRun, CourseRunEnrollment
from ecommerce.models import Discount


class ManagerContractListSerializer(serializers.ModelSerializer):
    """Serializer for listing contracts that a manager can access."""

    title = serializers.CharField(source="name")
    expiration_date = serializers.DateField(source="contract_end")
    price = serializers.DecimalField(
        source="enrollment_fixed_price",
        max_digits=10,
        decimal_places=2,
        allow_null=True,
    )

    class Meta:
        model = ContractPage
        fields = ["id", "title", "expiration_date", "max_learners", "price"]


class ManagerContractDetailSerializer(serializers.ModelSerializer):
    """Serializer for detailed contract view with statistics."""

    title = serializers.CharField(source="name")
    expiration_date = serializers.DateField(source="contract_end")
    price = serializers.DecimalField(
        source="enrollment_fixed_price",
        max_digits=10,
        decimal_places=2,
        allow_null=True,
    )

    # Statistics
    attachment_percentage = serializers.SerializerMethodField()
    total_enrollments = serializers.SerializerMethodField()
    total_codes = serializers.SerializerMethodField()

    class Meta:
        model = ContractPage
        fields = [
            "id",
            "title",
            "expiration_date",
            "max_learners",
            "price",
            "attachment_percentage",
            "total_enrollments",
            "total_codes",
        ]

    def get_attachment_percentage(self, obj):
        """Calculate attachment percentage if seat-limited."""
        if not obj.max_learners:
            return None

        attached_count = obj.get_learners().count()
        return round((attached_count / obj.max_learners) * 100, 2)

    def get_total_enrollments(self, obj):
        """Get total number of enrollments across all contract course runs."""
        return CourseRunEnrollment.objects.filter(run__b2b_contract=obj).count()

    def get_total_codes(self, obj):
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
            "live",
        ]


class ManagerEnrollmentSerializer(serializers.ModelSerializer):
    """Serializer for enrollments in a specific course run."""

    learner_name = serializers.SerializerMethodField()
    learner_email = serializers.SerializerMethodField()
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

    def get_learner_name(self, obj):
        """Get the learner's full name."""
        return obj.user.get_full_name() or obj.user.username

    def get_learner_email(self, obj):
        """Get the learner's email address."""
        return obj.user.email


class ManagerEnrollmentCodeSerializer(serializers.ModelSerializer):
    """Serializer for enrollment codes available to a contract."""

    code = serializers.CharField(source="discount_code")
    is_redeemed = serializers.SerializerMethodField()

    class Meta:
        model = Discount
        fields = ["id", "code", "is_redeemed"]

    def get_is_redeemed(self, obj):
        """Check if this code has been used for contract attachment."""
        contract = self.context.get("contract")
        if not contract:
            return False

        return DiscountContractAttachmentRedemption.objects.filter(
            discount=obj, contract=contract
        ).exists()
