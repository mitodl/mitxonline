"""Management command to backfill email deliverability events for DiscountContractAttachmentRedemption records."""

from datetime import UTC, datetime

from django.core.management import BaseCommand

from b2b.api import is_later_event, is_trackable_event_type
from b2b.models import (
    DiscountContractAttachmentRedemption,
)

MAILGUN_LOGS_API_URL = "https://api.mailgun.net/v1/analytics/logs"
MAILGUN_LOGS_PAGE_LIMIT = 300
# Mailgun only retains log data for 30 days on paid plans, so there's no point asking further back than that.
MAILGUN_LOGS_RETENTION_DAYS = 30


class Command(BaseCommand):
    """Send a synthetic Mailgun webhook payload to the b2b webhook endpoint."""

    help = "Send a synthetic Mailgun webhook payload for a DiscountContractAttachmentRedemption to the ProcessMailgunWebhook endpoint."

    def add_arguments(self, parser):
        """Add arguments to the command."""

        parser.add_argument(
            "record_ids",
            type=str,
            default="",
            help="Comma-separated list of IDs of the DiscountContractAttachmentRedemption records to send webhooks for.",
        )
        parser.add_argument(
            "execute",
            action="store_true",
            default=False,
            help="When specified, persist the retrieved events to the database. Otherwise, just print them.",
        )

    def get_latest_event_for_message_ids(self, message_ids):
        pass

    # Same set of checks as in process_mailgun_webhook_for_enrollment_code_emails but without signature validation
    def should_persist_event(self, record, event):
        if not is_trackable_event_type(event) or not is_later_event(event, record):  # noqa: SIM103
            return False

        return True

    def handle(self, *args, **kwargs):  # noqa: ARG002

        record_ids = [int(record_id) for record_id in kwargs["record_ids"].split(",")]

        records = DiscountContractAttachmentRedemption.objects.filter(pk=record_ids)
        filtered_records = []
        for record in records:
            if not record.email_message_id:
                self.stdout.write(
                    f"Skipping record {record}, no email message ID found."
                )
            else:
                filtered_records.append(record)

        message_id_to_filtered_record = {
            filtered_record.email_message_id: filtered_record
            for filtered_record in filtered_records
        }
        latest_events_by_message_id = self.get_latest_event_for_message_ids(
            list(message_id_to_filtered_record.keys())
        )
        # Technically we aren't getting events back, we're getting logs.
        # We'll have to munge it into a format consistent w/ the webhooks
        for message_id, record in message_id_to_filtered_record.items():
            event = latest_events_by_message_id.get(message_id)
            if not event:
                self.stdout.write(f"Skipping record {record}, no event found.")
                continue

            if self.should_persist_event(record, event):
                if kwargs["execute"]:
                    self.stdout.write(
                        f"Persisting event status {event['event']} to record {record}."
                    )
                    record.email_status = event["event"]
                    record.email_status_event_timestamp = datetime.fromtimestamp(
                        event["timestamp"], tz=UTC
                    )
                    record.save()
                else:
                    self.stdout.write(
                        f"DRY RUN - Found event status {event['event']} to record {record}."
                    )
