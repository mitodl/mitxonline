"""
Management command to enroll learners into course runs in both edX and MITx Online.

By default, the command runs in dry-run mode (preview only). Use --commit to apply changes.

**Usage:**

1. Enroll all learners listed in a CSV file into a single course run (preview):
./manage.py enroll_learners --csv=learners.csv --run=course-v1:MITxT+14.310Fx+2T2026

2. Same, but actually create the enrollments:
./manage.py enroll_learners --csv=learners.csv --run=course-v1:MITxT+14.310Fx+2T2026 --commit

3. Enroll specific users into a course run:
./manage.py enroll_learners --users=user1@example.com,user2@example.com --run=course-v1:MITxT+14.310Fx+2T2026 --commit

4. Enroll users listed in a CSV file that specifies its own courseware_id per row
   (columns: email, courseware_id) instead of a single --run for every row:
./manage.py enroll_learners --csv=enrollments.csv --commit

5. Keep local enrollment records even if edX enrollment fails:
./manage.py enroll_learners --csv=learners.csv --run=course-v1:MITxT+14.310Fx+2T2026 --commit -k

Note: creating an enrollment via this command runs the normal enrollment business
logic (courses.api.create_run_enrollments), so it will also enroll the learner in
edX and send them the standard enrollment confirmation email. This command only
ever creates free "audit" enrollments (it never creates an Order/Product, so a
paid "verified" enrollment isn't possible here) -- use the site's normal
purchase flow, or `create_verified_enrollment`, for paid enrollments.
"""

import csv

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from courses.management.utils import bulk_enroll_learners
from courses.models import CourseRun
from openedx.constants import EDX_ENROLLMENT_AUDIT_MODE
from users.api import fetch_user

User = get_user_model()

# Accept a couple of common header spellings for the email column
EMAIL_COLUMN_ALIASES = ("email", "user", "user_email")


class Command(BaseCommand):
    """Enroll learners into course runs in both edX and MITx Online"""

    help = "Enroll learners into course runs in both edX and MITx Online"

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            type=str,
            help="Path to a CSV file with an email column (accepted headers: "
            f"{', '.join(EMAIL_COLUMN_ALIASES)}). May optionally include a "
            "'courseware_id' column to enroll different rows into different "
            "course runs; otherwise --run is used for every row.",
        )
        parser.add_argument(
            "--users",
            type=str,
            help="Comma-separated list of user emails or usernames",
        )
        parser.add_argument(
            "--run",
            type=str,
            help="The 'courseware_id' value for a CourseRun. Required with "
            "--users, and required with --csv unless the CSV has its own "
            "'courseware_id' column.",
        )
        parser.add_argument(
            "-k",
            "--keep-failed-enrollments",
            action="store_true",
            dest="keep_failed_enrollments",
            help="Keep local enrollment records even if edX enrollment fails",
        )
        parser.add_argument(
            "--commit",
            action="store_true",
            dest="commit",
            help="Actually perform enrollments. Without this flag, "
            "the command runs in dry-run mode (preview only).",
        )

    def _find_email_column(self, fieldnames):
        """Return the fieldname to use as the email column, or None if not found"""
        lowered = {name.lower().strip(): name for name in fieldnames}
        for alias in EMAIL_COLUMN_ALIASES:
            if alias in lowered:
                return lowered[alias]
        return None

    def _parse_csv(self, csv_path, default_courseware_id):
        """
        Parse CSV file and return list of (user_identifier, courseware_id) tuples.

        Args:
            csv_path (str): Path to the CSV file
            default_courseware_id (str | None): courseware_id to use for rows
                when the CSV has no 'courseware_id' column of its own

        Returns:
            list[tuple[str, str]]: List of (user_identifier, courseware_id) tuples
        """
        entries = []
        try:
            with open(csv_path, newline="") as f:  # noqa: PTH123
                reader = csv.DictReader(f)
                if not reader.fieldnames:
                    raise CommandError(f"CSV file is empty: {csv_path}")  # noqa: EM102

                email_column = self._find_email_column(reader.fieldnames)
                if email_column is None:
                    raise CommandError(
                        "CSV file must have an email column "  # noqa: EM102
                        f"(accepted headers: {', '.join(EMAIL_COLUMN_ALIASES)})"
                    )

                has_courseware_column = "courseware_id" in {
                    name.lower().strip() for name in reader.fieldnames
                }
                if not has_courseware_column and not default_courseware_id:
                    raise CommandError(
                        "--run is required when the CSV has no 'courseware_id' column"  # noqa: EM101
                    )

                for row_num, row in enumerate(reader, start=2):
                    email = (row.get(email_column) or "").strip()
                    courseware_id = (
                        row.get("courseware_id") or default_courseware_id or ""
                    ).strip()
                    if not email or not courseware_id:
                        self.stderr.write(
                            self.style.WARNING(
                                f"Row {row_num}: Skipping empty email or courseware_id"
                            )
                        )
                        continue
                    entries.append((email, courseware_id))
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

    def _dry_run(self, entries):
        """Preview which enrollments would be created without making changes."""
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

            self.stdout.write(
                f"  Would enroll: {user.email} in {cw_id} (mode={EDX_ENROLLMENT_AUDIT_MODE})"
            )
            succeeded += 1

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Summary: {succeeded} would be enrolled, {skipped} skipped"
            )
        )
        if succeeded > 0:
            self.stdout.write(
                self.style.WARNING("Re-run with --commit to apply changes.")
            )

    def _resolve_entries(self, csv_path, users_str, courseware_id):
        """Validate arguments and return the list of (user, courseware_id) entries."""
        if csv_path and users_str:
            raise CommandError("--csv cannot be combined with --users")  # noqa: EM101

        if users_str and not courseware_id:
            raise CommandError("--run is required when using --users")  # noqa: EM101

        if not csv_path and not users_str:
            raise CommandError("Provide --csv or --users with --run.")  # noqa: EM101

        if csv_path:
            entries = self._parse_csv(csv_path, courseware_id)
        else:
            entries = self._parse_inline_users(users_str, courseware_id)

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

        entries = self._resolve_entries(csv_path, users_str, courseware_id)

        dry_run = not commit
        self.stdout.write(
            f"Processing {len(entries)} enrollment(s)..."
            + (" (DRY RUN)" if dry_run else "")
        )

        if dry_run:
            self._dry_run(entries)
            return

        summary = bulk_enroll_learners(
            entries,
            mode=EDX_ENROLLMENT_AUDIT_MODE,
            keep_failed_enrollments=keep_failed,
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
