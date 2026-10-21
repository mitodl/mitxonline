"""
Management command to compare MITx Online upgrade deadlines with edX.

MITx Online owns CourseRun.upgrade_deadline and pushes changes to the edX
verified mode when a run is saved. Runs whose deadline was set only in edX
(the nightly pull from edX was removed in #3443) have a blank or stale value
here. This command lists those runs, and with --fix copies the edX date into
MITx Online.

Copying goes from edX to MITx Online, never the other way: some values here are
known to be wrong, and pushing them would overwrite correct dates in edX. The
one push --fix makes is for unpinned runs, where both sides already match: it
sends edX its own date back so edX marks it explicit.
"""

import csv
import time

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from mitol.common.utils.datetime import now_in_utc
from requests.exceptions import RequestException

from courses.models import CourseRun
from openedx.api import (
    get_edx_api_service_client,
    get_edx_mode_expiration,
    get_edx_verified_mode,
    sync_courserun_upgrade_deadline_to_edx,
)

STATUS_OK = "ok"
# Both have the same deadline, but edX hasn't marked it explicit, so every
# Studio publish recomputes it from the course end. --fix sends edX its own date
# back, which marks it explicit.
STATUS_UNPINNED = "unpinned"
# edX has a deadline and MITx Online doesn't.
STATUS_MXO_MISSING = "mxo_missing"
# Both have a deadline and they differ.
STATUS_MISMATCH = "mismatch"
# MITx Online has a deadline and edX doesn't, or edX's value couldn't be
# parsed. --fix can't help here. Only a save that changes the run's deadline
# queues a push; re-saving the same value doesn't.
STATUS_EDX_MISSING = "edx_missing"
STATUS_NO_VERIFIED_MODE = "no_verified_mode"
STATUS_ERROR = "error"

FIXABLE_STATUSES = {STATUS_MXO_MISSING, STATUS_MISMATCH}


def _isoformat(value):
    return value.isoformat() if value else ""


class Command(BaseCommand):
    """Compare upgrade deadlines in MITx Online with edX."""

    help = (
        "Compare CourseRun.upgrade_deadline with the expiration date of each run's "
        "verified mode in edX and print the result as CSV. With --fix, copy the "
        "edX date into MITx Online for runs where it's missing or different, and "
        "pin matching dates that edX hasn't marked explicit. Exits with an error "
        "if any run errored or couldn't be fixed."
    )

    def add_arguments(self, parser):
        """Add the command's arguments."""
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            "--run",
            type=str,
            help="The 'courseware_id' of a single CourseRun to check",
        )
        group.add_argument(
            "--all",
            action="store_true",
            help=(
                "Check every live, unexpired course run that hasn't ended yet "
                "(or has no end date)"
            ),
        )
        parser.add_argument(
            "--fix",
            action="store_true",
            help=(
                "Copy the edX deadline into MITx Online for runs that are "
                f"{' or '.join(sorted(FIXABLE_STATUSES))}, and send edX its own "
                f"date back for runs that are {STATUS_UNPINNED}"
            ),
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=0,
            help="Seconds to wait between edX requests (default: 0)",
        )
        super().add_arguments(parser)

    def get_runs(self, options):
        """Resolve the --run/--all options into a list of CourseRuns."""
        if options["run"]:
            run = CourseRun.all_objects.filter(courseware_id=options["run"]).first()
            if run is None:
                msg = f"Could not find run with courseware_id={options['run']}"
                raise CommandError(msg)
            return [run]

        now = now_in_utc()
        # Same selection as the nightly course sync, limited to runs that haven't
        # ended: a finished run's upgrade deadline no longer matters.
        return list(
            CourseRun.objects.live(include_b2b=True)
            .filter(Q(expiration_date__isnull=True) | Q(expiration_date__gt=now))
            .filter(Q(end_date__isnull=True) | Q(end_date__gt=now))
            .exclude(run_tag__startswith="fake-")
            .order_by("courseware_id")
        )

    def compare(self, run, client):
        """Return (status, edX deadline) for a run."""
        verified_mode = get_edx_verified_mode(run.courseware_id, client=client)
        if verified_mode is None:
            return STATUS_NO_VERIFIED_MODE, None

        edx_deadline = get_edx_mode_expiration(verified_mode)
        mxo_deadline = run.upgrade_deadline

        if mxo_deadline == edx_deadline:
            is_explicit = verified_mode.json.get("expiration_datetime_is_explicit")
            status = (
                STATUS_UNPINNED
                if edx_deadline is not None and is_explicit is not True
                else STATUS_OK
            )
        elif mxo_deadline is None:
            status = STATUS_MXO_MISSING
        elif edx_deadline is None:
            status = STATUS_EDX_MISSING
        else:
            status = STATUS_MISMATCH

        return status, edx_deadline

    def fix(self, run, status, edx_deadline, client):
        """
        Fix one run for --fix. Return the CSV's fixed column: "yes", "failed",
        or "" when the status isn't fixable.
        """
        if status in FIXABLE_STATUSES:
            run.upgrade_deadline = edx_deadline
            # save() rather than update() so the Fastly purge runs and Learn
            # picks up the new date. The push signal fires too, and re-sends the
            # date if edX hasn't marked it explicit.
            try:
                run.save(update_fields=["upgrade_deadline"])
            except ValidationError as exc:
                # save() runs clean(), which can reject a run for reasons
                # unrelated to its deadline. Report it and keep going.
                self.stderr.write(
                    self.style.ERROR(f"{run.courseware_id}: could not save: {exc}")
                )
                return "failed"
            return "yes"

        if status == STATUS_UNPINNED:
            try:
                sync_courserun_upgrade_deadline_to_edx(run, client=client)
            except RequestException as exc:
                self.stderr.write(
                    self.style.ERROR(
                        f"{run.courseware_id}: could not pin: "
                        f"{type(exc).__name__}: {exc}"
                    )
                )
                return "failed"
            return "yes"

        return ""

    def handle(self, *args, **options):  # noqa: ARG002
        """Handle command execution."""
        runs = self.get_runs(options)
        fix = options["fix"]
        delay = options["delay"]

        writer = csv.writer(self.stdout)
        writer.writerow(
            ["courseware_id", "mxo_deadline", "edx_deadline", "status", "fixed"]
        )

        # Reuse one client for the whole batch.
        client = get_edx_api_service_client()
        counts = {}
        fixed_count = 0
        failed_count = 0

        for index, run in enumerate(runs):
            if index and delay:
                time.sleep(delay)

            try:
                status, edx_deadline = self.compare(run, client)
            except RequestException as exc:
                # Keep going; one bad run (missing in edX, a 5xx) shouldn't stop
                # the report.
                self.stderr.write(
                    self.style.ERROR(
                        f"{run.courseware_id}: {type(exc).__name__}: {exc}"
                    )
                )
                status, edx_deadline = STATUS_ERROR, None

            counts[status] = counts.get(status, 0) + 1
            mxo_deadline = run.upgrade_deadline
            fixed = ""

            if fix:
                fixed = self.fix(run, status, edx_deadline, client)
                if fixed == "yes":
                    fixed_count += 1
                elif fixed == "failed":
                    failed_count += 1

            writer.writerow(
                [
                    run.courseware_id,
                    _isoformat(mxo_deadline),
                    _isoformat(edx_deadline),
                    status,
                    fixed,
                ]
            )

        summary = ", ".join(f"{status}: {count}" for status, count in counts.items())
        message = (
            f"Checked {len(runs)} run(s). {summary or 'nothing to check'}. "
            f"Fixed: {fixed_count}"
            + (f", failed: {failed_count}" if failed_count else "")
            + ("" if fix else " (run with --fix to copy edX dates into MITx Online)")
        )
        if counts.get(STATUS_ERROR) or failed_count:
            # The CSV is already written; fail so a script running this can tell.
            raise CommandError(message)
        self.stderr.write(message)
