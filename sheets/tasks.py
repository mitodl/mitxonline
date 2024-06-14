import logging
from django.core.cache import cache
from mitol.google_sheets_deferrals.api import DeferralRequestHandler
from mitol.google_sheets_refunds.api import RefundRequestHandler

from main.celery import app

log = logging.getLogger(__name__)


@app.task(bind=True)
def process_google_sheets_requests(self):
    """
    Task to process refund and deferral requests from Google sheets
    """
    # revoke all previously scheduled tasks
    # log.info(self.name)
    # log.info(app.signature(self.name))
    query = app.events.state.tasks_by_type(self.name)
    for uuid, task in query:
        app.control.revoke(uuid)

    refund_request_handler = RefundRequestHandler()
    deferral_request_handler = DeferralRequestHandler()
    if refund_request_handler.is_configured():
        refund_request_handler.process_sheet()

    if deferral_request_handler.is_configured():
        deferral_request_handler.process_sheet()
