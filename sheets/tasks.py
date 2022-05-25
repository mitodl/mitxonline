"""Sheets app tasks"""
import json
import logging
from itertools import chain, repeat

from googleapiclient.errors import HttpError
import celery

from celery import app
from sheets import (
    api as sheets_api,
    refund_request_api,
)
from sheets.constants import (
    SHEET_TYPE_COUPON_REQUEST,
    SHEET_TYPE_ENROLL_CHANGE,
    SHEET_TYPE_COUPON_ASSIGN,
)
from sheets.utils import AssignmentRowUpdate

log = logging.getLogger(__name__)


@app.task
def handle_unprocessed_refund_requests():
    """
    Ensures that all non-legacy rows in the spreadsheet are correctly represented in the database,
    reverses/refunds enrollments if appropriate, updates the spreadsheet to reflect any changes
    made, and returns a summary of those changes.
    """
    refund_request_handler = refund_request_api.RefundRequestHandler()
    results = refund_request_handler.process_sheet()
    return results


@app.task(
    autoretry_for=(HttpError,),
    retry_kwargs={"max_retries": 3, "countdown": 5},
    rate_limit="6/m",
)
def renew_file_watch(*, sheet_type, file_id):
    """
    Renews push notifications for changes to a certain spreadsheet via the Google API.
    """
    sheet_metadata = sheets_api.get_sheet_metadata_from_type(sheet_type)
    # These renewal tasks are run on a schedule and ensure that there is an unexpired file watch
    # on each sheet we want to watch. If a file watch was manually created/updated at any
    # point, this task might be run while that file watch is still unexpired. If the file
    # watch renewal was skipped, the task might not run again until after expiration. To
    # avoid that situation, the file watch is always renewed here (force=True).
    file_watch, created, _ = sheets_api.create_or_renew_sheet_file_watch(
        sheet_metadata, force=True, sheet_file_id=file_id
    )
    return {
        "type": sheet_metadata.sheet_type,
        "file_watch_channel_id": getattr(file_watch, "channel_id"),
        "file_watch_file_id": getattr(file_watch, "file_id"),
        "created": created,
    }


@app.task()
def renew_all_file_watches():
    """
    Renews push notifications for changes to all relevant spreadsheets via the Google API.
    """
    assignment_sheet_ids_to_renew = (
        coupon_assign_api.fetch_webhook_eligible_assign_sheet_ids()
    )
    sheet_type_file_id_pairs = chain(
        # The coupon request and enrollment change request sheets are singletons.
        # It's not necessary to specify their file id here.
        [(SHEET_TYPE_COUPON_REQUEST, None)],
        [(SHEET_TYPE_ENROLL_CHANGE, None)],
        zip(
            repeat(SHEET_TYPE_COUPON_ASSIGN, len(assignment_sheet_ids_to_renew)),
            assignment_sheet_ids_to_renew,
        ),
    )
    celery.group(
        *[
            renew_file_watch.s(sheet_type=sheet_type, file_id=file_id)
            for sheet_type, file_id in sheet_type_file_id_pairs
        ]
    )()
