"""Management command to backfill email deliverability events for DiscountContractAttachmentRedemption records."""

import email.utils
from datetime import UTC, datetime

import requests
from django.conf import settings
from django.core.management import BaseCommand, CommandError
from mitol.common.utils import now_in_utc

from b2b.api import is_later_event, is_trackable_event_type
from b2b.models import (
    MAILGUN_EMAIL_EVENT_TYPES,
    DiscountContractAttachmentRedemption,
)

MAILGUN_LOGS_API_URL = "https://api.mailgun.net/v1/analytics/logs"
MAILGUN_LOGS_PAGE_LIMIT = 100
MAILGUN_LOGS_DESC = "timestamp:desc"
# Mailgun only retains log data for 30 days, so there's no point asking further back than that.
MAILGUN_LOGS_RETENTION_DAYS = "30d"


# Normalize the response to have fields expected from webhooks. At the moment, its just timestamp which is misnamed
def _unpack_event_data_from_api_response(mailgun_log_response):
    mailgun_log_response["timestamp"] = datetime.fromisoformat(
        mailgun_log_response["@timestamp"]
    ).timestamp()
    return mailgun_log_response


class Command(BaseCommand):
    """Send a synthetic Mailgun webhook payload to the b2b webhook endpoint."""

    help = "Send a synthetic Mailgun webhook payload for a DiscountContractAttachmentRedemption to the ProcessMailgunWebhook endpoint."

    def add_arguments(self, parser):
        """Add arguments to the command."""

        parser.add_argument(
            "--record-ids",
            type=str,
            default="",
            required=True,
            help="Comma-separated list of IDs of the DiscountContractAttachmentRedemption records to send webhooks for.",
        )
        parser.add_argument(
            "--execute",
            action="store_true",
            default=False,
            help="When specified, persist the retrieved events to the database. Otherwise, just print them.",
        )

    def get_events_for_message_ids(self, message_ids):
        events_by_message_id = {}
        for message_id in message_ids:
            events_by_message_id[message_id] = [
                _unpack_event_data_from_api_response(event)
                for event in self.fetch_logs_for_message(message_id)
            ]
        return events_by_message_id

    def fetch_logs_for_message(self, message_id):
        """Page through POST /v1/analytics/logs for a single message_id."""
        items = []
        pagination = {"sort": MAILGUN_LOGS_DESC, "limit": MAILGUN_LOGS_PAGE_LIMIT}

        while True:
            body = {
                "end": email.utils.format_datetime(now_in_utc()),
                "duration": MAILGUN_LOGS_RETENTION_DAYS,
                "filter": {
                    "AND": [
                        {
                            "attribute": "message_id",
                            "comparator": "=",
                            "values": [{"label": message_id, "value": message_id}],
                        }
                    ]
                },
                "events": MAILGUN_EMAIL_EVENT_TYPES,
                "include_subaccounts": True,
                "pagination": pagination,
            }

            resp = requests.post(
                MAILGUN_LOGS_API_URL,
                json=body,
                headers={"Content-Type": "application/json"},
                auth=("api", settings.MAILGUN_KEY),
                timeout=30,
            )
            resp.raise_for_status()
            payload = resp.json()

            page_items = payload.get("items", [])
            items.extend(page_items)

            next_token = payload.get("pagination", {}).get("next")
            if not next_token or not page_items:
                break

            pagination = {
                "sort": MAILGUN_LOGS_DESC,
                "limit": MAILGUN_LOGS_PAGE_LIMIT,
                "token": next_token,
            }

        return items

    # Same set of checks as in process_mailgun_webhook_for_enrollment_code_emails but without signature validation
    def should_persist_event(self, record, event):
        if not is_trackable_event_type(event) or not is_later_event(event, record):  # noqa: SIM103
            return False

        return True

    def handle(self, *args, **kwargs):  # noqa: ARG002

        try:
            record_ids = [
                int(record_id) for record_id in kwargs["record_ids"].split(",")
            ]
        except ValueError:
            err = "Individual record IDs must be an integer."
            raise CommandError(err) from None

        records = DiscountContractAttachmentRedemption.objects.filter(pk__in=record_ids)
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
        latest_events_by_message_id = self.get_events_for_message_ids(
            list(message_id_to_filtered_record.keys())
        )
        # Technically we aren't getting events back, we're getting logs.
        # We'll have to munge it into a format consistent w/ the webhooks
        for message_id, record in message_id_to_filtered_record.items():
            events = latest_events_by_message_id.get(message_id)
            if not events:
                self.stdout.write(f"Skipping record {record}, no event found.")
                continue
            for event in events:
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
                    break
