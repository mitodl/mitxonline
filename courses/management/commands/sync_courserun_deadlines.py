"""
Management command to push MITx Online upgrade deadlines into edX course modes.

The CourseRun post_save signal handles ongoing edits. This command exists for
the cases the signal cannot cover: backfilling runs whose deadlines were set
before the sync existed, repairing runs whose edX copy was overwritten by a
Studio publish, and re-syncing after bulk queryset.update() edits.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from mitol.common.utils.datetime import now_in_utc

from courses.models import CourseRun
from openedx.api import (
    get_edx_api_service_client,
    sync_courserun_upgrade_deadline_to_edx,
)
from openedx.constants import UpgradeDeadlineSyncResult


class Command(BaseCommand):
    """Push upgrade deadlines from MITx Online into edX."""

    help = (
        "Push CourseRun.upgrade_deadline into the expiration_datetime of each "
        "run's verified course mode in edX."
    )

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            "--run",
            type=str,
            help="The 'courseware_id' of a single CourseRun to sync",
        )
        group.add_argument(
            "--all",
            action="store_true",
            help=(
                "Sync every live, unexpired course run that has an upgrade deadline set"
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be pushed without calling edX",
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
        # Runs with no deadline are skipped: edX's API cannot unset an existing
        # expiration date, so there is nothing useful to push for them.
        return list(
            CourseRun.objects.live(include_b2b=True)
            .filter(Q(expiration_date__isnull=True) | Q(expiration_date__gt=now))
            .filter(upgrade_deadline__isnull=False)
            .exclude(run_tag__startswith="fake-")
            .order_by("courseware_id")
        )

    def report_result(self, run, result):
        """Write a per-run line for the outcomes an operator needs to act on."""
        if result == UpgradeDeadlineSyncResult.UPDATED:
            self.stdout.write(f"{run.courseware_id}: set to {run.upgrade_deadline}")
        elif result == UpgradeDeadlineSyncResult.CLEAR_UNSUPPORTED:
            self.stdout.write(
                self.style.WARNING(
                    f"{run.courseware_id}: cleared here but edX cannot unset its "
                    f"deadline - clear it in the edX admin"
                )
            )
        elif result == UpgradeDeadlineSyncResult.NO_VERIFIED_MODE:
            self.stdout.write(
                self.style.WARNING(f"{run.courseware_id}: no verified mode in edX")
            )

    def handle(self, *args, **options):  # noqa: ARG002
        """Handle command execution."""
        runs = self.get_runs(options)

        if not runs:
            self.stdout.write("No matching course runs to sync.")
            return

        if options["dry_run"]:
            for run in runs:
                self.stdout.write(
                    f"Would push {run.upgrade_deadline} to {run.courseware_id}"
                )
            self.stdout.write(
                self.style.WARNING(f"Dry run: {len(runs)} run(s) not synced.")
            )
            return

        # One client for the whole batch rather than per run - each
        # get_edx_api_service_client() call refreshes an OAuth token.
        client = get_edx_api_service_client()
        counts = dict.fromkeys(UpgradeDeadlineSyncResult, 0)
        failures = []

        for run in runs:
            try:
                result = sync_courserun_upgrade_deadline_to_edx(run, client=client)
            except Exception as exc:  # noqa: BLE001
                # Keep going through the batch; one bad run (missing in edX,
                # expired token, 5xx) should not strand the rest.
                failures.append((run.courseware_id, str(exc)))
                self.stderr.write(self.style.ERROR(f"{run.courseware_id}: {exc}"))
                continue

            counts[result] += 1
            self.report_result(run, result)

        if counts[UpgradeDeadlineSyncResult.DISABLED]:
            self.stdout.write(
                self.style.WARNING(
                    "FEATURE_SYNC_UPGRADE_DEADLINE_TO_EDX is off - "
                    f"{counts[UpgradeDeadlineSyncResult.DISABLED]} run(s) skipped."
                )
            )

        summary = ", ".join(
            f"{result.value}: {count}" for result, count in counts.items() if count
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Sync complete for {len(runs)} run(s). "
                f"{summary or 'nothing to do'}. failed: {len(failures)}"
            )
        )
