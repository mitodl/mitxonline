# ruff: noqa: PLC0415
"""Tasks for the B2B app."""

import logging

from django.core.cache import cache
from django.db.models import Q

from b2b.mail import (
    send_enrollment_code_assignment_email,
    send_test_enrollment_code_assignment_email,
)
from main.celery import app

log = logging.getLogger(__name__)


@app.task()
def queue_enrollment_code_check(contract_id: int):
    """Queue the ensure_enrollment_codes_exist call."""
    from b2b.api import ensure_enrollment_codes_exist
    from b2b.models import ContractPage

    contract = ContractPage.objects.get(id=contract_id)
    ensure_enrollment_codes_exist(contract)


@app.task(acks_late=True)
def push_upgraded_enrollments_to_edx(enrollment_ids: list[int]):
    """
    Push enrollments that were upgraded to verified locally into edX.

    Each enrollment is pushed on its own, so one bad run doesn't block the
    rest. Failures are left with edx_enrolled=False for
    retry_failed_edx_enrollments to pick up.
    """
    from courses.models import CourseRunEnrollment
    from openedx.api import enroll_in_edx_course_runs

    enrollments = CourseRunEnrollment.objects.filter(
        id__in=enrollment_ids, edx_enrolled=False
    ).select_related("user", "run")

    for enrollment in enrollments:
        try:
            enroll_in_edx_course_runs(
                enrollment.user, [enrollment.run], mode=enrollment.enrollment_mode
            )
        except Exception:  # noqa: BLE001
            log.warning(
                "Couldn't push upgraded enrollment %s to edX, leaving it for retry",
                enrollment.id,
                exc_info=True,
            )
            continue

        enrollment.edx_enrolled = True
        enrollment.save_and_log(None)


@app.task(acks_late=True)
def queue_organization_sync():
    """Queue the sync_organizations call."""
    from b2b.api import reconcile_keycloak_orgs

    reconcile_keycloak_orgs()


@app.task(bind=True)
def create_program_contract_runs(
    self, contract_id: int, program_id: int, org_prefix: str | None = None
):
    """
    Create contract runs for all courses in a program.

    Uses lock-based debouncing - only one task runs at a time per contract/program pair.

    Args:
        contract_id: The ID of the ContractPage
        program_id: The ID of the Program
    """
    from b2b.contracts import add_courseware_to_contract
    from b2b.models import ContractPage
    from courses.models import Program

    lock_key = f"create_program_contract_runs_lock:{contract_id}:{program_id}"
    lock_acquired = cache.add(lock_key, self.request.id, timeout=3600)

    if not lock_acquired:
        log.info(
            "Task already running for contract %s and program %s, skipping duplicate",
            contract_id,
            program_id,
        )
        return

    try:
        contract = ContractPage.objects.get(id=contract_id)
        program = Program.objects.get(id=program_id)

        added = add_courseware_to_contract(contract, program, org_prefix=org_prefix)

        log.info(
            "Completed contract run creation for program %s in contract %s: "
            "%d created, %d courses without a usable source run",
            program.readable_id,
            contract.slug,
            added.runs_added,
            added.courses_without_source_run,
        )

    finally:
        # Always release the lock when done, even if an exception occurred
        cache.delete(lock_key)


@app.task(acks_late=True)
def queue_contract_sheet_update_post_save(
    contract_id: int, *, only_update: bool = False
):
    """
    Take an appropriate action on post-save for the contract.

    If the prior revision to the current has a different tab or sheet URL
    specified, then run write_codes, which will set up the (presumably blank)
    sheet. Otherwise, use update_sheet, which is non-destructive.
    """

    from b2b.models import ContractPage
    from b2b.sheets import ContractEnrollmentCodesSheetHandler

    contract = ContractPage.objects.get(pk=contract_id)

    try:
        handler = ContractEnrollmentCodesSheetHandler(contract)
    except ValueError as exc:
        if "Google Sheet" in str(exc):
            log.info(
                "Contract %s has no linked Google Sheet or tab set, skipping", contract
            )
        elif "managed" in str(exc):
            log.info("Contract %s is managed (no enrollment codes), skipping", contract)
        return

    if not only_update:
        has_revs = contract.revisions.count() > 1

        if has_revs:
            # We have page revisions so check to see if the sheet or the tab changed
            # in between. If they did, then we start over.
            # Explicitly set this sort even though the Wagtail model seems to do this anyway.
            revs = contract.revisions.order_by("-created_at").all()[:2]
            if (
                revs[0].as_object().google_sheet_target
                != revs[1].as_object().google_sheet_target
            ) or (
                revs[0].as_object().google_sheet_target_tab
                != revs[1].as_object().google_sheet_target_tab
            ):
                has_revs = False

    if not only_update and not has_revs:
        log.info("Setting up Google Sheet for %s", contract)

        codes_written = handler.write_codes()
    else:
        log.info("Updating Google Sheet for %s", contract)

        codes_written = handler.update_sheet()

    log.info("Wrote %s codes for %s", codes_written, contract)


@app.task(acks_late=True)
def queue_update_all_contract_enrollment_sheets():
    """
    Update all of the configured enrollment code sheets in the system.

    This fires off a bunch of calls to the above post-save task rather than rolling
    through the sequentially. May need to revisit this (add batching, etc) as we
    add more contracts.
    """

    from b2b.constants import CONTRACT_MEMBERSHIP_AUTOS
    from b2b.models import ContractPage

    updateable_contracts = (
        ContractPage.objects.exclude(
            Q(membership_type__in=CONTRACT_MEMBERSHIP_AUTOS) | Q(google_sheet_target="")
        )
        .only("id")
        .all()
    )

    for contract in updateable_contracts:
        queue_contract_sheet_update_post_save.delay(contract.id, only_update=True)


@app.task()
def queue_send_enrollment_code_assignment_email(assignment_record_ids: list[int]):
    send_enrollment_code_assignment_email(assignment_record_ids)


@app.task()
def queue_send_test_enrollment_code_assignment_email(
    email: str, contract_record_id: int
):
    send_test_enrollment_code_assignment_email(email, contract_record_id)


# At the moment, we only process webhooks for b2b admin dashboard-sent emails and throw out the rest.
# As a result, we don't wanna track results for this task as most are no-ops
@app.task(ignore_result=True)
def queue_process_mailgun_webhook_for_enrollment_code_emails(payload):
    from b2b.api import process_mailgun_webhook_for_enrollment_code_emails

    process_mailgun_webhook_for_enrollment_code_emails(payload)
