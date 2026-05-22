"""
Management command to unenroll learners from course runs in both edX and MITx Online.

By default, the command runs in dry-run mode (preview only). Use --commit to apply changes.

**Usage:**

1. Unenroll all active learners from a course run (preview):
./manage.py unenroll_learners --run=course-v1:MITx+6.00.1x+2024

2. Unenroll specific users from a course run:
./manage.py unenroll_learners --users=user1@example.com,user2@example.com --run=course-v1:MITx+6.00.1x+2024 --commit

3. Unenroll users listed in a CSV file (columns: user, courseware_id):
./manage.py unenroll_learners --csv=unenrollments.csv --commit

4. Suppress unenrollment emails:
./manage.py unenroll_learners --run=course-v1:MITx+6.00.1x+2024 --commit --no-email

5. Keep local enrollment records even if edX unenrollment fails:
./manage.py unenroll_learners --users=user1@example.com --run=course-v1:MITx+6.00.1x+2024 --commit -k
"""

import csv

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from courses.management.utils import bulk_unenroll_learners
from courses.models import CourseRun, CourseRunEnrollment
from users.api import fetch_user

User = get_user_model()


class Command(BaseCommand):
    """Unenroll learners from course runs in both edX and MITx Online"""

    help = "Unenroll learners from course runs in both edX and MITx Online"

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            type=str,
            help="Path to a CSV file with columns: user, courseware_id",
        )
        parser.add_argument(
            "--users",
            type=str,
            help="Comma-separated list of user emails or usernames",
        )
        parser.add_argument(
            "--run",
            type=str,
            help="The 'courseware_id' value for a CourseRun. "
            "When used alone, unenrolls ALL active learners from this run. "
            "When used with --users, scopes unenrollment to those users.",
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

    def _parse_csv(self, csv_path):
        """
        Parse CSV file and return list of (user_identifier, courseware_id) tuples.

        Args:
            csv_path (str): Path to the CSV file

        Returns:
            list[tuple[str, str]]: List of (user_identifier, courseware_id) tuples
        """
        entries = []
        try:
            with open(csv_path, newline="") as f:  # noqa: PTH123
                reader = csv.DictReader(f)
                if not reader.fieldnames or not {"user", "courseware_id"}.issubset(
                    set(reader.fieldnames)
                ):
                    raise CommandError(
                        "CSV file must have 'user' and 'courseware_id' columns"  # noqa: EM101
                    )
                for row_num, row in enumerate(reader, start=2):
                    user_val = row["user"].strip()
                    courseware_id = row["courseware_id"].strip()
                    if not user_val or not courseware_id:
                        self.stderr.write(
                            self.style.WARNING(
                                f"Row {row_num}: Skipping empty user or courseware_id"
                            )
                        )
                        continue
                    entries.append((user_val, courseware_id))
        except FileNotFoundError:
            raise CommandError(f"CSV file not found: {csv_path}")  # noqa: B904, EM102
        return entries

    def _parse_inline_users(self, users_str, courseware_id):
        """
        Parse inline users string and return list of (user_identifier, courseware_id) tuples.

        Args:
            users_str (str): Comma-separated user emails/usernames
            courseware_id (str): The courseware_id for the course run

        Returns:
            list[tuple[str, str]]: List of (user_identifier, courseware_id) tuples
        """
        return [(u.strip(), courseware_id) for u in users_str.split(",") if u.strip()]

    def _entries_for_run(self, courseware_id):
        """
        Build entries list for all active enrollments in a course run.

        Args:
            courseware_id (str): The courseware_id for the course run

        Returns:
            list[tuple[str, str]]: List of (user_email, courseware_id) tuples
        """
        course_run = CourseRun.objects.filter(courseware_id=courseware_id).first()
        if course_run is None:
            raise CommandError(
                f"Could not find course run with courseware_id={courseware_id}"  # noqa: EM102
            )
        enrollments = CourseRunEnrollment.objects.filter(
            run=course_run, active=True
        ).select_related("user")
        return [(e.user.email, courseware_id) for e in enrollments]

    def _dry_run(self, entries):
        """Preview which enrollments would be unenrolled without making changes."""
        succeeded = 0
        skipped = 0
        run_cache = {}

        for user_identifier, cw_id in entries:
            try:
                user = fetch_user(user_identifier)
            except User.DoesNotExist:
                self.stderr.write(
                    self.style.WARNING(f"SKIP: User not found: {user_identifier}")
                )
                skipped += 1
                continue

            if cw_id not in run_cache:
                run_cache[cw_id] = CourseRun.objects.filter(courseware_id=cw_id).first()
            course_run = run_cache[cw_id]
            if course_run is None:
                self.stderr.write(
                    self.style.WARNING(f"SKIP: Course run not found: {cw_id}")
                )
                skipped += 1
                continue

            enrollment = CourseRunEnrollment.objects.filter(
                user=user, run=course_run
            ).first()
            if enrollment is None or not enrollment.active:
                self.stderr.write(
                    self.style.WARNING(
                        f"SKIP: No active enrollment for {user.email} in {cw_id}"
                    )
                )
                skipped += 1
            else:
                self.stdout.write(f"  Would unenroll: {user.email} from {cw_id}")
                succeeded += 1

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Summary: {succeeded} would be unenrolled, {skipped} skipped"
            )
        )
        if succeeded > 0:
            self.stdout.write(
                self.style.WARNING("Re-run with --commit to apply changes.")
            )

    def _resolve_entries(self, csv_path, users_str, courseware_id):
        """Validate arguments and return the list of (user, courseware_id) entries."""
        if csv_path and (users_str or courseware_id):
            raise CommandError(
                "--csv cannot be combined with --users or --run"  # noqa: EM101
            )

        if users_str and not courseware_id:
            raise CommandError("--run is required when using --users")  # noqa: EM101

        if not csv_path and not users_str and not courseware_id:
            raise CommandError(
                "Provide --csv, --users with --run, or --run alone "  # noqa: EM101
                "to unenroll all active learners from a course run."
            )

        if csv_path:
            entries = self._parse_csv(csv_path)
        elif users_str:
            entries = self._parse_inline_users(users_str, courseware_id)
        else:
            entries = self._entries_for_run(courseware_id)

        if not entries:
            raise CommandError("No valid entries found to process")  # noqa: EM101

        return entries

    def handle(self, *args, **options):  # noqa: ARG002
        """Handle command execution"""
        csv_path = options.get("csv")
        users_str = options.get("users")
        courseware_id = options.get("run")
        keep_failed = options.get("keep_failed_enrollments")
        commit = options.get("commit")
        no_email = options.get("no_email")

        entries = self._resolve_entries(csv_path, users_str, courseware_id)

        dry_run = not commit
        self.stdout.write(
            f"Processing {len(entries)} unenrollment(s)..."
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
