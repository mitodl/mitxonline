"""Tests for ManagerEnrollmentCodeSerializer."""

import pytest
from django.utils import timezone

from b2b.factories import ContractPageFactory
from b2b.models import (
    REDEMPTION_STATUS_ASSIGNED,
    REDEMPTION_STATUS_REDEEMED,
    REDEMPTION_STATUS_UNASSIGNED,
    DiscountContractAttachmentRedemption,
)
from b2b.serializers.v0.manager import ManagerEnrollmentCodeSerializer
from ecommerce.factories import DiscountFactory
from users.factories import UserFactory

pytestmark = [pytest.mark.django_db]


@pytest.fixture
def contract():
    return ContractPageFactory.create()


@pytest.fixture
def discount():
    return DiscountFactory.create()


def _serialize(discount, redemptions=None):
    """Helper: attach prefetched_redemptions and run the serializer."""
    discount.prefetched_redemptions = redemptions if redemptions is not None else []
    return ManagerEnrollmentCodeSerializer(discount).data


class TestManagerEnrollmentCodeSerializerUnassigned:
    def test_code_field_maps_discount_code(self, discount):
        data = _serialize(discount)
        assert data["code"] == discount.discount_code

    def test_id_field(self, discount):
        data = _serialize(discount)
        assert data["id"] == discount.id

    def test_redemption_status_is_unassigned(self, discount):
        data = _serialize(discount)
        assert data["redemption_status"] == REDEMPTION_STATUS_UNASSIGNED

    def test_assigned_to_is_none(self, discount):
        data = _serialize(discount)
        assert data["assigned_to"] is None

    def test_assigned_on_is_none(self, discount):
        data = _serialize(discount)
        assert data["assigned_on"] is None

    def test_assigned_name_is_none(self, discount):
        data = _serialize(discount)
        assert data["assigned_name"] is None

    def test_redeemed_on_is_none(self, discount):
        data = _serialize(discount)
        assert data["redeemed_on"] is None

    def test_redeemed_by_is_none(self, discount):
        data = _serialize(discount)
        assert data["redeemed_by"] is None

    def test_last_sent_is_none(self, discount):
        data = _serialize(discount)
        assert data["last_sent"] is None

    def test_no_prefetched_redemptions_attr(self, discount):
        """Serializer should handle the case where the attribute is absent."""
        # Do not set prefetched_redemptions at all
        data = ManagerEnrollmentCodeSerializer(discount).data
        assert data["redemption_status"] == REDEMPTION_STATUS_UNASSIGNED
        assert data["assigned_to"] is None


class TestManagerEnrollmentCodeSerializerAssigned:
    def test_redemption_status_is_assigned(self, discount, contract):
        redemption = DiscountContractAttachmentRedemption.objects.create(
            discount=discount,
            contract=contract,
            assigned_email="learner@example.com",
            assigned_name="Test Learner",
        )
        data = _serialize(discount, [redemption])
        assert data["redemption_status"] == REDEMPTION_STATUS_ASSIGNED

    def test_assigned_to_email(self, discount, contract):
        redemption = DiscountContractAttachmentRedemption.objects.create(
            discount=discount,
            contract=contract,
            assigned_email="learner@example.com",
        )
        data = _serialize(discount, [redemption])
        assert data["assigned_to"] == "learner@example.com"

    def test_assigned_on_is_populated(self, discount, contract):
        redemption = DiscountContractAttachmentRedemption.objects.create(
            discount=discount,
            contract=contract,
            assigned_email="learner@example.com",
        )
        data = _serialize(discount, [redemption])
        assert data["assigned_on"] is not None

    def test_assigned_name(self, discount, contract):
        redemption = DiscountContractAttachmentRedemption.objects.create(
            discount=discount,
            contract=contract,
            assigned_email="learner@example.com",
            assigned_name="Test Learner",
        )
        data = _serialize(discount, [redemption])
        assert data["assigned_name"] == "Test Learner"

    def test_redeemed_on_is_none_when_not_redeemed(self, discount, contract):
        redemption = DiscountContractAttachmentRedemption.objects.create(
            discount=discount,
            contract=contract,
            assigned_email="learner@example.com",
        )
        data = _serialize(discount, [redemption])
        assert data["redeemed_on"] is None

    def test_redeemed_by_is_none_when_not_redeemed(self, discount, contract):
        redemption = DiscountContractAttachmentRedemption.objects.create(
            discount=discount,
            contract=contract,
            assigned_email="learner@example.com",
        )
        data = _serialize(discount, [redemption])
        assert data["redeemed_by"] is None

    def test_last_sent_populated_when_set(self, discount, contract):
        now = timezone.now()
        redemption = DiscountContractAttachmentRedemption.objects.create(
            discount=discount,
            contract=contract,
            assigned_email="learner@example.com",
            last_reminder_sent_on=now,
        )
        data = _serialize(discount, [redemption])
        assert data["last_sent"] is not None

    def test_last_sent_is_none_when_not_set(self, discount, contract):
        redemption = DiscountContractAttachmentRedemption.objects.create(
            discount=discount,
            contract=contract,
            assigned_email="learner@example.com",
        )
        data = _serialize(discount, [redemption])
        assert data["last_sent"] is None

    def test_blank_assigned_name_serialized_as_empty_string(self, discount, contract):
        redemption = DiscountContractAttachmentRedemption.objects.create(
            discount=discount,
            contract=contract,
            assigned_email="learner@example.com",
            assigned_name="",
        )
        data = _serialize(discount, [redemption])
        assert data["assigned_name"] == ""


class TestManagerEnrollmentCodeSerializerRedeemed:
    def test_redemption_status_redeemed_when_user_set(self, discount, contract):
        user = UserFactory.create()
        redemption = DiscountContractAttachmentRedemption.objects.create(
            discount=discount,
            contract=contract,
            assigned_email=user.email,
            user=user,
        )
        data = _serialize(discount, [redemption])
        assert data["redemption_status"] == REDEMPTION_STATUS_REDEEMED

    def test_redemption_status_redeemed_when_redeemed_on_set(self, discount, contract):
        redemption = DiscountContractAttachmentRedemption.objects.create(
            discount=discount,
            contract=contract,
            assigned_email="learner@example.com",
            redeemed_on=timezone.now(),
        )
        data = _serialize(discount, [redemption])
        assert data["redemption_status"] == REDEMPTION_STATUS_REDEEMED

    def test_redeemed_by_returns_user_email(self, discount, contract):
        user = UserFactory.create(email="redeemer@example.com")
        redemption = DiscountContractAttachmentRedemption.objects.create(
            discount=discount,
            contract=contract,
            assigned_email=user.email,
            user=user,
        )
        data = _serialize(discount, [redemption])
        assert data["redeemed_by"] == "redeemer@example.com"

    def test_redeemed_on_is_populated(self, discount, contract):
        now = timezone.now()
        redemption = DiscountContractAttachmentRedemption.objects.create(
            discount=discount,
            contract=contract,
            assigned_email="learner@example.com",
            redeemed_on=now,
        )
        data = _serialize(discount, [redemption])
        assert data["redeemed_on"] is not None

    def test_redeemed_by_none_when_no_user(self, discount, contract):
        """redeemed_on set but no user linked — redeemed_by should be None."""
        redemption = DiscountContractAttachmentRedemption.objects.create(
            discount=discount,
            contract=contract,
            assigned_email="learner@example.com",
            redeemed_on=timezone.now(),
        )
        data = _serialize(discount, [redemption])
        assert data["redeemed_by"] is None

    def test_assigned_to_still_populated_after_redemption(self, discount, contract):
        user = UserFactory.create(email="redeemer@example.com")
        redemption = DiscountContractAttachmentRedemption.objects.create(
            discount=discount,
            contract=contract,
            assigned_email="redeemer@example.com",
            user=user,
        )
        data = _serialize(discount, [redemption])
        assert data["assigned_to"] == "redeemer@example.com"


class TestManagerEnrollmentCodeSerializerPrefetchBehavior:
    def test_uses_first_redemption_in_list(self, discount, contract):
        """When multiple redemptions are in the list, the first is used."""
        user = UserFactory.create()
        first = DiscountContractAttachmentRedemption.objects.create(
            discount=discount,
            contract=contract,
            assigned_email="first@example.com",
            user=user,
        )
        second = DiscountContractAttachmentRedemption.objects.create(
            discount=discount,
            contract=contract,
            assigned_email="second@example.com",
        )
        data = _serialize(discount, [first, second])
        assert data["assigned_to"] == "first@example.com"
        assert data["redemption_status"] == REDEMPTION_STATUS_REDEEMED

    def test_empty_prefetched_list_treated_as_unassigned(self, discount):
        data = _serialize(discount, [])
        assert data["redemption_status"] == REDEMPTION_STATUS_UNASSIGNED

    def test_fields_present_in_output(self, discount):
        data = _serialize(discount)
        expected_fields = {
            "id",
            "code",
            "redemption_status",
            "assigned_to",
            "assigned_on",
            "assigned_name",
            "redeemed_on",
            "redeemed_by",
            "last_sent",
        }
        assert set(data.keys()) == expected_fields
