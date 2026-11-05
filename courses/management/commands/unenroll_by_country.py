"""
Management command to bulk-unenroll learners whose legal address is in a
given country, in both edX and MITx Online.

By default, the command runs in dry-run mode (preview only). Use --commit to apply changes.

**Usage:**

1. Unenroll all active learners from every course run whose legal address
   country is Iran (preview):
./manage.py unenroll_by_country --country=IR

2. Actually perform the unenrollments:
./manage.py unenroll_by_country --country=IR --commit

3. Scope the unenrollment to a single course run:
./manage.py unenroll_by_country --country=IR --run=course-v1:MITx+6.00.1x+2024 --commit

4. Suppress unenrollment emails:
./manage.py unenroll_by_country --country=IR --commit --no-email

5. Keep local enrollment records even if edX unenrollment fails:
./manage.py unenroll_by_country --country=IR --commit -k
"""

from django.core.management.base import BaseCommand, CommandError

from courses.management.utils import bulk_unenroll_learners
from courses.models import CourseRunEnrollment


class Command(BaseCommand):
    """Bulk-unenroll learners from a given country in both edX and MITx Online"""

    help = "Bulk-unenroll learners whose legal address is in a given country"

    def add_arguments(self, parser):
        parser.add_argument(
            "--country",
            type=str,
            required=True,
            help="ISO 3166-1 alpha-2 country code to unenroll learners from (e.g. IR)",
        )
        parser.add_argument(
            "--run",
            type=str,
            help="Optional 'courseware_id' value for a CourseRun. When provided, "
            "scopes unenrollment to active enrollments in that run only. "
            "When omitted, unenrolls from every active enrollment for "
            "the given country.",
        )
        parser.add_argument(
            "-k",
            "--keep-failed-enrollments",
            action="store_true",
            dest="keep_failed_enrollments",
            help="Keep local enrollment records even if edX unenrollment fails",
        )
        parser.add_argument(
            "--commit",
            action="store_true",
            dest="commit",
            help="Actually perform unenrollments. Without this flag, "
            "the command runs in dry-run mode (preview only).",
        )
        parser.add_argument(
            "--no-email",
            action="store_true",
            dest="no_email",
            help="Suppress unenrollment notification emails to learners",
        )

    def _entries_for_country(self, country_code, courseware_id=None):
        """
        Build entries list for all active enrollments held by learners whose
        legal address is in the given country.

        Args:
            country_code (str): ISO 3166-1 alpha-2 country code
            courseware_id (str or None): If given, restricts to this course run

        Returns:
            list[tuple[str, str]]: List of (user_email, courseware_id) tuples
        """
        enrollments = CourseRunEnrollment.objects.filter(
            user__legal_address__country=country_code,
            active=True,
        ).select_related("user", "run")
        if courseware_id:
            enrollments = enrollments.filter(run__courseware_id=courseware_id)
        return [(e.user.email, e.run.courseware_id) for e in enrollments]

    def _dry_run(self, entries):
        """Preview which enrollments would be unenrolled without making changes."""
        for user_email, cw_id in entries:
            self.stdout.write(f"  Would unenroll: {user_email} from {cw_id}")

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(f"Summary: {len(entries)} would be unenrolled")
        )
        if entries:
            self.stdout.write(
                self.style.WARNING("Re-run with --commit to apply changes.")
            )

    def handle(self, *args, **options):  # noqa: ARG002
        """Handle command execution"""
        country_code = options["country"].strip().upper()
        courseware_id = options.get("run")
        keep_failed = options.get("keep_failed_enrollments")
        commit = options.get("commit")
        no_email = options.get("no_email")

        if len(country_code) != 2:  # noqa: PLR2004
            raise CommandError(
                "--country must be an ISO 3166-1 alpha-2 code (e.g. IR)"  # noqa: EM101
            )

        entries = self._entries_for_country(country_code, courseware_id)
        if not entries:
            raise CommandError(
                f"No active enrollments found for country={country_code}"  # noqa: EM102
            )

        dry_run = not commit
        self.stdout.write(
            f"Processing {len(entries)} unenrollment(s) for country={country_code}..."
            + (" (DRY RUN)" if dry_run else "")
        )

        if dry_run:
            self._dry_run(entries)
            return

        summary = bulk_unenroll_learners(
            entries,
            keep_failed_enrollments=keep_failed,
            send_notification=not no_email,
        )

        # Print details
        for _user_id, _cw_id, status, message in summary["details"]:
            if status == "succeeded":
                self.stdout.write(self.style.SUCCESS(f"  {message}"))
            elif status == "skipped":
                self.stderr.write(self.style.WARNING(f"  SKIP: {message}"))
            else:
                self.stderr.write(self.style.ERROR(f"  FAILED: {message}"))

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Summary: {summary['succeeded']} succeeded, "
                f"{summary['failed']} failed, {summary['skipped']} skipped"
            )
        )
