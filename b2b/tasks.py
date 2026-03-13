# ruff: noqa: PLC0415
"""Tasks for the B2B app."""

import logging

from django.core.cache import cache
from django.db.models import Q

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
    from django.db.models import Q

    from b2b.api import create_contract_run
    from b2b.models import ContractPage
    from courses.models import CourseRun, Program

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

        if hasattr(program, "_courses_with_requirements_data"):
            delattr(program, "_courses_with_requirements_data")

        created_count = 0
        skipped_count = 0

        # Get courses with source runs
        courses_with_source = program.courses_qset.filter(
            Q(courseruns__is_source_run=True) | Q(courseruns__run_tag="SOURCE")
        )

        # Count courses without source runs
        courses_without_source = program.courses_qset.exclude(
            Q(courseruns__is_source_run=True) | Q(courseruns__run_tag="SOURCE")
        ).count()

        # Create contract runs for each course
        for course in courses_with_source:
            # Determine what the new run ID would be
            clone_course_run = course.courseruns.filter(
                Q(is_source_run=True) | Q(run_tag="SOURCE")
            ).first()

            if not clone_course_run:
                continue

            # Check if run already exists
            if CourseRun.objects.filter(course=course, b2b_contract=contract).exists():
                skipped_count += 1
                log.debug(
                    "Contract run already exists for course %s in contract %s",
                    course.readable_id,
                    contract.slug,
                )
                continue

            # Create the run
            create_contract_run(contract, course, org_prefix=org_prefix)
            created_count += 1
            log.info(
                "Created contract run for course %s in program %s for contract %s",
                course.readable_id,
                program.readable_id,
                contract.slug,
            )

        log.info(
            "Completed contract run creation for program %s in contract %s: "
            "%d created, %d skipped, %d courses without source runs",
            program.readable_id,
            contract.slug,
            created_count,
            skipped_count,
            courses_without_source,
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
            rev_count = contract.revisions.count()
            revs = contract.revisions.all()[rev_count - 2 :]
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
