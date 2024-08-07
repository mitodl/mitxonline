import logging

from celery.exceptions import SoftTimeLimitExceeded
from mitol.google_sheets_deferrals.api import DeferralRequestHandler
from mitol.google_sheets_refunds.api import RefundRequestHandler

from main.celery import app

log = logging.getLogger(__name__)


@app.task(time_limit=120, soft_time_limit=60)
def process_google_sheets_requests():
    """
    Task to process refund and deferral requests from Google sheets
    """
    try:
        refund_request_handler = RefundRequestHandler()
        deferral_request_handler = DeferralRequestHandler()
        if refund_request_handler.is_configured():
            refund_request_handler.process_sheet()

        if deferral_request_handler.is_configured():
            deferral_request_handler.process_sheet()
    except SoftTimeLimitExceeded:
        log.info("Google sheets requests exceeded time limit")
