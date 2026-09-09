"""Transfer course-related user records from one user to another."""

from argparse import RawTextHelpFormatter

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from mitol.common.utils.datetime import now_in_utc

from courses.models import (
    CourseRunCertificate,
    CourseRunEnrollment,
    CourseRunGrade,
    ProgramCertificate,
    ProgramEnrollment,
)
from users.api import fetch_user

User = get_user_model()


class Command(BaseCommand):
    """
    Transfer course-related records between two users.

    Moves course run enrollments, grades, and certificates - for course runs
    that have already ended - plus program enrollments and certificates, from
    one user to another, matching users by email address. A course run with
    no end_date is treated as not yet ended and its records are left with the
    source user.

    A record is skipped, not aborted, if the destination user already has a
    matching enrollment/grade/certificate; transferred and skipped counts are
    reported at the end.

    Example: transfer_user_course_records --from_email=old@example.com --to_email=new@example.com
    """

    help = __doc__

    def add_arguments(self, parser):
        """Add command line arguments."""
        parser.formatter_class = RawTextHelpFormatter
        parser.add_argument(
            "--from_email",
            "--from-email",
            dest="from_email",
            type=str,
            required=True,
            help="Email address for the user records should be moved from",
        )
        parser.add_argument(
            "--to_email",
            "--to-email",
            dest="to_email",
            type=str,
            required=True,
            help="Email address for the user records should be moved to",
        )
        super().add_arguments(parser)

    def handle(self, *args, **options):  # noqa: ARG002
        """Handle command execution."""
        source_user = self._fetch_user(options["from_email"], "from_email")
        destination_user = self._fetch_user(options["to_email"], "to_email")

        if source_user.pk == destination_user.pk:
            raise CommandError("Source and destination users must be different.")  # noqa: EM101

        source_records = self._load_source_records(source_user)
        to_transfer, skipped_counts = self._partition_conflicts(
            source_records, destination_user
        )

        with transaction.atomic():
            transfer_counts = self._transfer_records(to_transfer, destination_user)

        self._print_result(
            source_user, destination_user, transfer_counts, skipped_counts
        )

    def _fetch_user(self, email, option_name):
        """Look up a user by email and normalize fetch errors to CommandError."""
        try:
            return fetch_user(email)
        except User.DoesNotExist as exc:
            msg = f"Could not find user for --{option_name}={email}."
            raise CommandError(msg) from exc

    def _load_source_records(self, source_user):
        """
        Load all transfer candidates for the source user.

        Course run enrollments/grades/certificates only include runs that
        have already ended (end_date set and in the past) - a run with no
        end_date is treated as not yet ended, matching CourseRun.is_past, and
        is excluded. Program enrollments/certificates aren't tied to a single
        course run, so they aren't filtered by end date.
        """
        now = now_in_utc()
        ended_run = {"run__end_date__isnull": False, "run__end_date__lt": now}
        ended_course_run = {
            "course_run__end_date__isnull": False,
            "course_run__end_date__lt": now,
        }

        return {
            "course_run_enrollments": list(
                CourseRunEnrollment.all_objects.filter(
                    user=source_user, **ended_run
                ).select_related("run")
            ),
            "program_enrollments": list(
                ProgramEnrollment.all_objects.filter(user=source_user).select_related(
                    "program"
                )
            ),
            "course_run_grades": list(
                CourseRunGrade.objects.filter(
                    user=source_user, **ended_course_run
                ).select_related("course_run")
            ),
            "course_run_certificates": list(
                CourseRunCertificate.all_objects.filter(
                    user=source_user, **ended_course_run
                ).select_related("course_run")
            ),
            "program_certificates": list(
                ProgramCertificate.all_objects.filter(user=source_user).select_related(
                    "program"
                )
            ),
        }

    def _partition_conflicts(self, source_records, destination_user):
        """
        Split source records into ones safe to transfer and ones the
        destination user already has a matching record for (by the field
        each model's unique-with-user constraint is defined on). Conflicting
        records are skipped rather than aborting the whole transfer.

        Returns (to_transfer, skipped_counts).
        """
        conflicting_run_ids = set(
            CourseRunEnrollment.all_objects.filter(user=destination_user).values_list(
                "run_id", flat=True
            )
        )
        conflicting_program_ids = set(
            ProgramEnrollment.all_objects.filter(user=destination_user).values_list(
                "program_id", flat=True
            )
        )
        conflicting_graded_run_ids = set(
            CourseRunGrade.objects.filter(user=destination_user).values_list(
                "course_run_id", flat=True
            )
        )
        conflicting_cert_run_ids = set(
            CourseRunCertificate.all_objects.filter(user=destination_user).values_list(
                "course_run_id", flat=True
            )
        )
        conflicting_cert_program_ids = set(
            ProgramCertificate.all_objects.filter(user=destination_user).values_list(
                "program_id", flat=True
            )
        )

        to_transfer = {
            "course_run_enrollments": [
                enrollment
                for enrollment in source_records["course_run_enrollments"]
                if enrollment.run_id not in conflicting_run_ids
            ],
            "program_enrollments": [
                enrollment
                for enrollment in source_records["program_enrollments"]
                if enrollment.program_id not in conflicting_program_ids
            ],
            "course_run_grades": [
                grade
                for grade in source_records["course_run_grades"]
                if grade.course_run_id not in conflicting_graded_run_ids
            ],
            "course_run_certificates": [
                certificate
                for certificate in source_records["course_run_certificates"]
                if certificate.course_run_id not in conflicting_cert_run_ids
            ],
            "program_certificates": [
                certificate
                for certificate in source_records["program_certificates"]
                if certificate.program_id not in conflicting_cert_program_ids
            ],
        }
        skipped_counts = {
            label: len(source_records[label]) - len(to_transfer[label])
            for label in source_records
        }
        return to_transfer, skipped_counts

    def _transfer_records(self, to_transfer, destination_user):
        """Transfer each record set and return counts by label."""
        for enrollment in to_transfer["course_run_enrollments"]:
            enrollment.user = destination_user
            enrollment.save_and_log(None)

        for enrollment in to_transfer["program_enrollments"]:
            enrollment.user = destination_user
            enrollment.save_and_log(None)

        for grade in to_transfer["course_run_grades"]:
            grade.user = destination_user
            grade.save_and_log(None)

        for certificate in to_transfer["course_run_certificates"]:
            certificate.user = destination_user
            certificate.save(update_fields=["user"])

        for certificate in to_transfer["program_certificates"]:
            certificate.user = destination_user
            certificate.save(update_fields=["user"])

        return {label: len(records) for label, records in to_transfer.items()}

    def _print_result(
        self, source_user, destination_user, transfer_counts, skipped_counts
    ):
        """Print a summary of what was transferred and what was skipped."""
        self.stdout.write(
            self.style.SUCCESS(
                "Transferred records from {source_email} to {destination_email}: "
                "{counts}".format(
                    source_email=source_user.email,
                    destination_email=destination_user.email,
                    counts=", ".join(
                        f"{label}={count}" for label, count in transfer_counts.items()
                    ),
                )
            )
        )
        if any(skipped_counts.values()):
            self.stdout.write(
                self.style.WARNING(
                    "Skipped (destination already has a matching record): "
                    + ", ".join(
                        f"{label}={count}"
                        for label, count in skipped_counts.items()
                        if count
                    )
                )
            )
