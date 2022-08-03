import logging
from mitol.google_sheets_refunds.api import RefundRequestHandler

from main.celery import app
from django.conf import settings

log = logging.getLogger(__name__)


@app.task
def process_refund_requests():
    """
    Task to process refund requests from Google sheets
    """
    if settings.MITOL_GOOGLE_SHEETS_DRIVE_CLIENT_ID is None:
        log.warning("MITOL_GOOGLE_SHEETS_DRIVE_CLIENT_ID is not set")

    refund_request_handler = RefundRequestHandler()
    refund_request_handler.process_sheet()
