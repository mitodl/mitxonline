"""
Management command to retire (delist) a course run.

Retiring a run makes it inert: its course and enrollment windows are pushed
into the past in edX *and* locally, it stops being live, and its products are
switched off. Existing enrollments are left alone by default so that learners
who were partway through keep their access to the material.

By default the command runs in dry-run mode and changes nothing. A snapshot of
the run's pre-retirement state is written either way, so there is always a
record to roll back from by hand.

**Usage:**

1. See what would happen (no changes, not even in edX):
./manage.py retire_courserun --run=course-v1:UAI_ACME+14.100x+1T12C2026

2. Retire the run, moving it to the B2B holding contract. Active learners keep
   their enrollments and their access; they are reported, not blocked:
./manage.py retire_courserun --run=course-v1:UAI_ACME+14.100x+1T12C2026 --commit

3. Retire and unenroll everyone. This revokes courseware access, so it refuses
   unless --allow-active-enrollments is passed too. Add --email to notify the
   learners, which is off by default:
./manage.py retire_courserun --run=... --commit --unenroll --allow-active-enrollments

4. Retire a run that has no counterpart in edX:
./manage.py retire_courserun --run=... --commit --skip-edx
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from mitol.common.utils.datetime import now_in_utc

from b2b.api import (
    RetirementContractCollisionError,
    move_run_to_retirement_contract,
)
from courses.management.utils import bulk_unenroll_learners
from courses.models import CourseRun
from courses.retirement import (
    SourceRunRetirementError,
    audit_course_run,
    build_snapshot,
    check_run_retirable,
    retire_course_run,
)
from openedx.api import get_edx_course


class Command(BaseCommand):
    """Retire a course run in both edX and MITx Online."""

    help = "Retire (delist) a course run in both edX and MITx Online."

    def add_arguments(self, parser):
        """Add command line arguments."""

        parser.add_argument(
            "--run",
            type=str,
            required=True,
            help="The 'courseware_id' value for the CourseRun to retire.",
        )
        parser.add_argument(
            "--commit",
            action="store_true",
            dest="commit",
            help="Actually retire the run. Without this flag, the command runs "
            "in dry-run mode and makes no changes in edX or MITx Online.",
        )
        parser.add_argument(
            "--unenroll",
            action="store_true",
            dest="unenroll",
            help="Unenroll the run's learners in edX and MITx Online. This "
            "revokes their access to the courseware, so it is off by default.",
        )
        parser.add_argument(
            "--allow-active-enrollments",
            action="store_true",
            dest="allow_active_enrollments",
            help="Required to combine --unenroll with a run that still has "
            "active learners on it. Retiring on its own never needs this: it "
            "leaves enrollments intact, so learners keep their access.",
        )
        parser.add_argument(
            "--email",
            action="store_true",
            dest="email",
            help="Send unenrollment notification emails. Only meaningful with "
            "--unenroll. Off by default so retirement is silent to learners.",
        )
        parser.add_argument(
            "--keep-contract",
            action="store_true",
            dest="keep_contract",
            help="Leave the run attached to its current B2B contract instead of "
            "moving it to the retirement holding contract.",
        )
        parser.add_argument(
            "--keep-products",
            action="store_true",
            dest="keep_products",
            help="Leave the run's products active.",
        )
        parser.add_argument(
            "--skip-edx",
            action="store_true",
            dest="skip_edx",
            help="Don't read from or write to edX. Use for runs that have no "
            "edX counterpart. The next sync will not overwrite the local dates "
            "only if the run genuinely isn't in edX.",
        )
        parser.add_argument(
            "--snapshot-dir",
            type=str,
            dest="snapshot_dir",
            default=".",
            help="Directory to write the pre-retirement snapshot to. Defaults "
            "to the current directory.",
        )
        parser.add_argument(
            "--reason",
            type=str,
            default="",
            help="Why the run is being retired. Recorded in the snapshot.",
        )

    def _resolve_run(self, courseware_id):
        """
        Find the run and refuse the ones we shouldn't touch.

        Uses all_objects because the default manager excludes source runs, and
        we need to be able to see a source run in order to reject it.
        """

        run = CourseRun.all_objects.filter(courseware_id=courseware_id).first()

        if run is None:
            msg = f"Could not find course run with courseware_id={courseware_id}"
            raise CommandError(msg)

        try:
            check_run_retirable(run)
        except SourceRunRetirementError as exc:
            raise CommandError(str(exc)) from exc

        return run

    def _report(self, audit):
        """Print the audit for the operator."""

        run = audit.run

        self.stdout.write("")
        self.stdout.write(f"Course run:   {run.courseware_id} (id={run.id})")
        self.stdout.write(f"Course:       {run.course.readable_id}")
        self.stdout.write(f"Title:        {run.title}")
        self.stdout.write(
            f"Run tag:      {run.run_tag}  language: {run.language or '-'}"
        )
        self.stdout.write(f"Live:         {run.live}")
        self.stdout.write(f"Start / end:  {run.start_date} / {run.end_date}")
        self.stdout.write(
            f"Enrollment:   {run.enrollment_start} / {run.enrollment_end}"
        )
        self.stdout.write(
            f"B2B contract: {run.b2b_contract or '- (not a contract run)'}"
        )

        self.stdout.write("")
        if audit.edx_error:
            self.stdout.write(
                self.style.WARNING(f"edX lookup failed: {audit.edx_error}")
            )
        elif audit.edx_details:
            self.stdout.write("edX currently reports:")
            for key, value in audit.edx_details.items():
                self.stdout.write(f"  {key}: {value}")
        else:
            self.stdout.write("edX not consulted (--skip-edx).")

        self.stdout.write("")
        self.stdout.write(
            f"Enrollments:  {len(audit.active_enrollments)} active, "
            f"{len(audit.inactive_enrollments)} inactive"
        )
        for enrollment in audit.active_enrollments:
            self.stdout.write(
                f"  ACTIVE  {enrollment.user.email} ({enrollment.enrollment_mode})"
            )
        if audit.certificate_count or audit.grade_count:
            self.stdout.write(
                self.style.WARNING(
                    f"  {audit.certificate_count} certificate(s) and "
                    f"{audit.grade_count} grade record(s) exist for this run. "
                    "These are kept either way."
                )
            )

        self.stdout.write("")
        self.stdout.write(f"Products:     {len(audit.products)}")
        for entry in audit.products:
            state = "active" if entry.was_active else "inactive"
            self.stdout.write(
                f"  #{entry.product.id} {entry.product.description} "
                f"({entry.product.price}, {state}), "
                f"{len(entry.discounts)} discount code(s), "
                f"{entry.basket_items} open basket item(s)"
            )
            if entry.discounts:
                self.stdout.write(
                    self.style.WARNING(
                        "    Discount codes are NOT removed by this command. "
                        "They will stop working once the product is inactive."
                    )
                )

    def _write_snapshot(self, audit, snapshot_dir, reason):
        """Write the rollback snapshot and return its path."""

        snapshot = build_snapshot(audit, reason=reason, source="Management Command")

        safe_id = audit.run.courseware_id.replace(":", "_").replace("+", "_")
        timestamp = now_in_utc().strftime("%Y%m%dT%H%M%SZ")
        target = Path(snapshot_dir) / f"retire_{safe_id}_{timestamp}.json"

        target.parent.mkdir(parents=True, exist_ok=True)
        # default=str so an unexpected object from the edX client can never be
        # the thing that aborts a retirement. The snapshot is a safety net; it
        # should degrade to a string rather than raise.
        target.write_text(json.dumps(snapshot, indent=2, default=str))

        return target.resolve()

    def _handle_contract(self, run, *, keep_contract):
        """Move the run to the holding contract, if it's a contract run."""

        if keep_contract or not run.b2b_contract_id:
            return

        previous = str(run.b2b_contract)

        try:
            contract = move_run_to_retirement_contract(run)
        except RetirementContractCollisionError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(f"  Moved from '{previous}' to '{contract}'")
        )

    def _handle_unenroll(self, run, *, email):
        """Unenroll the run's active learners."""

        entries = [
            (enrollment.user.email, run.courseware_id)
            for enrollment in run.enrollments.filter(active=True).select_related("user")
        ]

        if not entries:
            self.stdout.write("  No active enrollments to remove.")
            return

        summary = bulk_unenroll_learners(
            entries,
            keep_failed_enrollments=False,
            send_notification=email,
        )

        for _user_id, _cw_id, status, message in summary["details"]:
            if status == "succeeded":
                self.stdout.write(self.style.SUCCESS(f"  {message}"))
            elif status == "skipped":
                self.stderr.write(self.style.WARNING(f"  SKIP: {message}"))
            else:
                self.stderr.write(self.style.ERROR(f"  FAILED: {message}"))

        self.stdout.write(
            f"  Unenrolled {summary['succeeded']}, failed {summary['failed']}, "
            f"skipped {summary['skipped']}"
        )

    def _verify(self, run, *, skip_edx):
        """Re-read the run and report anything that didn't stick."""

        run.refresh_from_db()

        problems = []

        if run.live:
            problems.append("run is still live")
        if not run.end_date or run.end_date > now_in_utc():
            problems.append("end_date is not in the past")
        if not run.enrollment_end or run.enrollment_end > now_in_utc():
            problems.append("enrollment_end is not in the past")

        if not skip_edx:
            try:
                edx_run = get_edx_course(run.courseware_id)
                self.stdout.write(
                    f"  edX now reports end={getattr(edx_run, 'end', None)}, "
                    f"enrollment_end={getattr(edx_run, 'enrollment_end', None)}"
                )
            except Exception as exc:  # noqa: BLE001
                problems.append(f"could not re-read the run from edX: {exc}")

        if problems:
            self.stderr.write(
                self.style.ERROR("Verification found problems: " + "; ".join(problems))
            )
        else:
            self.stdout.write(self.style.SUCCESS("  Verification passed."))

    def handle(self, *args, **options):  # noqa: ARG002
        """Handle command execution."""

        commit = options["commit"]
        skip_edx = options["skip_edx"]

        run = self._resolve_run(options["run"])

        # An active product parked in the holding contract is a hazard: the
        # holding contract is 'managed' with no fixed price, so a later
        # `b2b_codes validate` sweep would treat it as a free SSO contract and
        # delete its discounts. Deactivating the products keeps the contract
        # inert, because ContractPage.get_products() filters on is_active.
        if (
            options["keep_products"]
            and run.b2b_contract_id
            and not options["keep_contract"]
        ):
            msg = (
                "--keep-products cannot be combined with moving the run to the "
                "retirement holding contract. Leaving an active product on a run "
                "parked in the holding contract risks a later b2b_codes sweep "
                "deleting its discounts. Add --keep-contract if you really want "
                "the products left on."
            )
            raise CommandError(msg)

        audit = audit_course_run(run, fetch_edx=not skip_edx)
        self._report(audit)

        snapshot_path = self._write_snapshot(
            audit, options["snapshot_dir"], options["reason"]
        )
        self.stdout.write("")
        self.stdout.write(f"Snapshot written to {snapshot_path}")

        if not commit:
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(
                    "DRY RUN - nothing was changed. Re-run with --commit to retire "
                    "this run."
                )
            )
            return

        # Retiring on its own is safe for people already on the run: no view
        # filters enrollments on live/end_date/expiration_date, and edX access
        # is governed purely by the enrollment record. So the refusal belongs on
        # --unenroll, which is the step that actually takes access away.
        if (
            options["unenroll"]
            and audit.has_active_enrollments
            and not options["allow_active_enrollments"]
        ):
            msg = (
                f"--unenroll would remove {len(audit.active_enrollments)} active "
                f"enrollment(s) from {run.courseware_id}, revoking those learners' "
                "access to the courseware. Re-run with --allow-active-enrollments "
                "if that is what you want, or drop --unenroll to retire the run "
                "and leave them enrolled."
            )
            raise CommandError(msg)

        self.stdout.write("")
        self.stdout.write("Retiring...")

        result = retire_course_run(
            run,
            deactivate_products=not options["keep_products"],
            skip_edx=skip_edx,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"  Dates set to start={result['dates']['start']}, "
                f"end={result['dates']['end']}, "
                f"enrollment_end={result['dates']['enrollment_end']}"
            )
        )
        self.stdout.write(self.style.SUCCESS("  live set to False"))

        if not skip_edx and not result["edx_updated"]:
            self.stderr.write(
                self.style.ERROR(
                    "  edX did not receive the enrollment window. The next "
                    "courseware sync will overwrite the local dates."
                )
            )

        for product in result["products"]:
            self.stdout.write(
                self.style.SUCCESS(f"  Deactivated product #{product.id}")
            )

        self._handle_contract(run, keep_contract=options["keep_contract"])

        if options["unenroll"]:
            self._handle_unenroll(run, email=options["email"])

        self.stdout.write("")
        self.stdout.write("Verifying...")
        self._verify(run, skip_edx=skip_edx)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Retired {run.courseware_id}."))
        self.stdout.write(f"Snapshot for rollback: {snapshot_path}")
