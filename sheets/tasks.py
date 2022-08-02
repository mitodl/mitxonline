from mitol.google_sheets_refunds.api import RefundRequestHandler

from main.celery import app


@app.task
def process_refund_requests():
    """
    Task to sync titles and dates for course runs from edX.
    """
    refund_request_handler = RefundRequestHandler()
    refund_request_handler.process_sheet()
