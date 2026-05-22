"""
Management command to unenroll learners from course runs in both edX and MITx Online.

**Usage:**

1. Unenroll a single user from a course run:
./manage.py unenroll_learners --users=user@example.com --run=course-v1:MITx+6.00.1x+2024

2. Unenroll specific users (inline) from a course run:
./manage.py unenroll_learners --users=user1@example.com,user2@example.com --run=course-v1:MITx+6.00.1x+2024

3. Unenroll users listed in a CSV file (columns: user, courseware_id):
./manage.py unenroll_learners --csv=unenrollments.csv

4. Dry run (preview only, no changes):
./manage.py unenroll_learners --csv=unenrollments.csv --dry-run

5. Keep local enrollment records even if edX unenrollment fails:
./manage.py unenroll_learners --users=user1@example.com --run=course-v1:MITx+6.00.1x+2024 -k
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
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            "--csv",
            type=str,
            help="Path to a CSV file with columns: user, courseware_id",
        )
        group.add_argument(
            "--users",
            type=str,
            help="Comma-separated list of user emails or usernames",
        )
        parser.add_argument(
            "--run",
            type=str,
            help="The 'courseware_id' value for a CourseRun (required with --users)",
        )
        parser.add_argument(
            "-k",
            "--keep-failed-enrollments",
            action="store_true",
            dest="keep_failed_enrollments",
            help="Keep local enrollment records even if edX unenrollment fails",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            dest="dry_run",
            help="Preview which enrollments would be unenrolled without making changes",
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
                    raise CommandError(  # noqa: TRY301
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
        return [
            (u.strip(), courseware_id)
            for u in users_str.split(",")
            if u.strip()
        ]

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
                run_cache[cw_id] = CourseRun.objects.filter(
                    courseware_id=cw_id
                ).first()
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

    def handle(self, *args, **options):  # noqa: ARG002
        """Handle command execution"""
        csv_path = options.get("csv")
        users_str = options.get("users")
        courseware_id = options.get("run")
        keep_failed = options.get("keep_failed_enrollments")
        dry_run = options.get("dry_run")

        if users_str and not courseware_id:
            raise CommandError("--run is required when using --users")  # noqa: EM101

        if csv_path:
            entries = self._parse_csv(csv_path)
        else:
            entries = self._parse_inline_users(users_str, courseware_id)

        if not entries:
            raise CommandError("No valid entries found to process")  # noqa: EM101

        self.stdout.write(
            f"Processing {len(entries)} unenrollment(s)..."
            + (" (DRY RUN)" if dry_run else "")
        )

        if dry_run:
            self._dry_run(entries)
            return

        summary = bulk_unenroll_learners(
            entries, keep_failed_enrollments=keep_failed
        )

        # Print details
        for user_id, cw_id, status, message in summary["details"]:
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
