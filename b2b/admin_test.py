"""Tests for b2b admin actions."""

from datetime import UTC, datetime

import pytest
from django.contrib import admin as django_admin

from b2b.admin import DiscountContractAttachmentRedemptionAdmin
from b2b.factories import ContractPageFactory
from b2b.models import (
    EMAIL_STATUS_DELIVERED,
    DiscountContractAttachmentRedemption,
)
from ecommerce.factories import DiscountFactory

pytestmark = [pytest.mark.django_db]


@pytest.fixture
def redemption():
    """A redemption with a message ID, eligible for backfill."""

    return DiscountContractAttachmentRedemption.objects.create(
        discount=DiscountFactory.create(),
        contract=ContractPageFactory.create(),
        assigned_email="learner@example.com",
        email_message_id="message-id-1",
    )


@pytest.fixture
def redemption_without_message_id():
    """A redemption with no message ID, ineligible for backfill."""

    return DiscountContractAttachmentRedemption.objects.create(
        discount=DiscountFactory.create(),
        contract=ContractPageFactory.create(),
        assigned_email="other-learner@example.com",
    )


def test_backfill_email_events_action(
    rf, mocker, redemption, redemption_without_message_id
):
    """The backfill action should persist the latest trackable event for records with a message ID."""
    event_timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    mocker.patch(
        "b2b.admin.get_events_for_message_ids",
        return_value={
            redemption.email_message_id: [
                {
                    "event": EMAIL_STATUS_DELIVERED,
                    "timestamp": event_timestamp.timestamp(),
                }
            ]
        },
    )
    mocker.patch.object(DiscountContractAttachmentRedemptionAdmin, "message_user")

    admin_instance = DiscountContractAttachmentRedemptionAdmin(
        DiscountContractAttachmentRedemption, django_admin.site
    )
    queryset = DiscountContractAttachmentRedemption.objects.filter(
        id__in=[redemption.id, redemption_without_message_id.id]
    )

    admin_instance.backfill_email_events(rf.post("/"), queryset)

    redemption.refresh_from_db()
    redemption_without_message_id.refresh_from_db()

    assert redemption.email_status == EMAIL_STATUS_DELIVERED
    assert redemption.email_status_event_timestamp == event_timestamp
    assert redemption_without_message_id.email_status == ""
    assert redemption_without_message_id.email_status_event_timestamp is None
