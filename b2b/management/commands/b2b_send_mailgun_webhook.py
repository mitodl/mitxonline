"""Management command to send a synthetic Mailgun webhook payload."""

import time
import uuid

import requests
from django.conf import settings
from django.core.management import BaseCommand, CommandError
from django.urls import reverse

from b2b.mail import ENROLLMENT_CODE_ASSINGMENT_TAG
from b2b.models import MAILGUN_EMAIL_EVENT_TYPES, DiscountContractAttachmentRedemption

# Static signature block - signature validation is expected to be disabled
# (MAILGUN_WEBHOOK_VALIDATE_SIGNATURE=False) when using this command.
STATIC_SIGNATURE = {
    "token": "FAKETOKEN",
    "timestamp": "1784746313",
    "signature": "FAKESIGNATURE",
}


def build_payload(message_id, event_type, recipient):
    """Build a synthetic Mailgun webhook payload."""

    return {
        "signature": STATIC_SIGNATURE,
        "event-data": {
            "event": event_type,
            "id": uuid.uuid4().hex,
            "timestamp": time.time(),
            "flags": {
                "is-authenticated": True,
                "is-big": False,
                "is-routed": False,
                "is-system-test": False,
                "is-test-mode": False,
            },
            "log-level": "info",
            "message": {
                "attachments": [],
                "headers": {
                    "message-id": message_id,
                    "from": settings.MAILGUN_FROM_EMAIL,
                    "to": recipient,
                    "subject": "You've been invited to MIT Learn",
                },
                "size": 13282,
            },
            "recipient": recipient,
            "recipient-domain": recipient.rsplit("@", 1)[-1],
            "tags": [ENROLLMENT_CODE_ASSINGMENT_TAG],
            "storage": {
                "key": "FAKEKEY",
                "url": f"https://storage-us-east4.api.mailgun.net/v3/domains/{settings.MAILGUN_SENDER_DOMAIN}/messages/BAABAAVQDEkfMMr0W9JFSbULXMTIJvQvYw",
            },
            "api-key-id": "a4da91cf-337932c5",
            "recipient-provider": "Outlook 365",
            "primary-dkim": f"pdk1._domainkey.{settings.MAILGUN_SENDER_DOMAIN}",
            "campaigns": [],
            "account": {"id": "FAKEACCOUNTID"},
            "delivery-status": {
                "attempt-no": 1,
                "code": 250,
                "message": "2.6.0 OK",
                "description": "",
                "session-seconds": 1.905,
                "enhanced-code": "2.6.0",
                "mx-host": "mit-edu.mail.protection.outlook.com",
                "mx-host-ip": "52.101.10.5",
                "certificate-verified": True,
                "tls": True,
                "utf8": True,
                "first-delivery-attempt-seconds": 0.045,
            },
            "domain": {"name": settings.MAILGUN_SENDER_DOMAIN},
            "envelope": {
                "sender": f"postmaster@{settings.MAILGUN_SENDER_DOMAIN}",
                "targets": recipient,
                "transport": "smtp",
                "sending-ip": "159.135.224.229",
            },
            "user-variables": {},
        },
    }


class Command(BaseCommand):
    """Send a synthetic Mailgun webhook payload to the b2b webhook endpoint."""

    help = "Send a synthetic Mailgun webhook payload for a DiscountContractAttachmentRedemption to the ProcessMailgunWebhook endpoint."

    def add_arguments(self, parser):
        """Add arguments to the command."""

        parser.add_argument(
            "record_id",
            type=int,
            help="The ID of the DiscountContractAttachmentRedemption record to send a webhook for.",
        )
        parser.add_argument(
            "event_type",
            type=str,
            choices=MAILGUN_EMAIL_EVENT_TYPES,
            help="The Mailgun event type to simulate.",
        )
        parser.add_argument(
            "--message-id",
            type=str,
            dest="message_id",
            default=None,
            help="Mailgun message ID to use. If not supplied, one is generated and saved to the record.",
        )
        parser.add_argument(
            "--host",
            type=str,
            default=None,
            help="Base URL to send the webhook to. Defaults to settings.SITE_BASE_URL.",
        )

    def handle(self, *args, **kwargs):  # noqa: ARG002
        """Send the synthetic webhook payload. This won't work with signature validation enabled"""

        record_id = kwargs["record_id"]
        event_type = kwargs["event_type"]
        host = kwargs["host"] or settings.SITE_BASE_URL

        try:
            record = DiscountContractAttachmentRedemption.objects.get(pk=record_id)
        except DiscountContractAttachmentRedemption.DoesNotExist:
            msg = f"DiscountContractAttachmentRedemption {record_id} does not exist."
            raise CommandError(msg) from None

        message_id = kwargs["message_id"] or (
            f"{uuid.uuid4().hex}@{settings.MAILGUN_SENDER_DOMAIN}"
        )
        record.email_message_id = message_id
        record.save()

        self.stdout.write(f"Using message ID {message_id} for record {record_id}.")

        payload = build_payload(
            message_id=message_id,
            event_type=event_type,
            recipient=record.assigned_email or "learner@example.com",
        )

        url = host.rstrip("/") + reverse("b2b:mailgun-webhook")
        response = requests.post(url, json=payload, timeout=30)

        self.stdout.write(f"POST {url} -> {response.status_code}")
        self.stdout.write(response.text)

        if response.ok:
            self.stdout.write(self.style.SUCCESS("Webhook sent."))
        else:
            self.stdout.write(self.style.ERROR("Webhook request failed."))
