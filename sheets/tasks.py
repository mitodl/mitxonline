import logging
from mitol.google_sheets_refunds.api import RefundRequestHandler

from main.celery import app

log = logging.getLogger(__name__)


@app.task
def process_refund_requests():
    """
    Task to process refund requests from Google sheets
    """
    refund_request_handler = RefundRequestHandler()
    if not refund_request_handler.is_configured():
        log.warning("MITOL_GOOGLE_SHEETS_* are not set")
        return
    refund_request_handler.process_sheet()
