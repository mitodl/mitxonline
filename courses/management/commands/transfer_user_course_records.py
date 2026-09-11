"""Transfer course-related user records from one user to another."""

from argparse import RawTextHelpFormatter

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from mitol.common.utils.datetime import now_in_utc

from courses.models import (
    CourseRunCertificate,
    CourseRunEnrollment,
    CourseRunGrade,
    PaidCourseRun,
    ProgramCertificate,
    ProgramEnrollment,
)
from ecommerce.models import Order, OrderStatus
from openedx.constants import EDX_ENROLLMENTS_PAID_MODES
from users.api import fetch_user

User = get_user_model()

# How to identify a skipped record of each kind in the summary output.
_SKIPPED_RECORD_IDENTIFIER = {
    "course_run_enrollments": lambda record: record.run.courseware_id,
    "course_run_grades": lambda record: record.course_run.courseware_id,
    "course_run_certificates": lambda record: record.course_run.courseware_id,
    "program_enrollments": lambda record: record.program.readable_id,
    "program_certificates": lambda record: record.program.readable_id,
}


class Command(BaseCommand):
    """
    Transfer course-related records between two users.

    Moves, for the source user:
    - Verified (paid) course run enrollments for course runs that have
      already ended. Audit course run enrollments are left alone - they're
      never moved. A course run with no end_date is treated as not yet ended
      and is excluded too.
    - Course run grades and certificates for those same ended course runs.
    - Program enrollments and certificates, unconditionally - independent of
      enrollment mode (verified or audit) and with no "ended" concept, since
      neither applies at the program level the way they do for a course run.
    - The FULFILLED Order(s) and PaidCourseRun record(s) backing each
      verified course run enrollment that transfers, so the payment record -
      and the "already paid for this" check it drives - follows the
      enrollment instead of staying attributed to the source user.

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
        to_transfer, skipped_records = self._partition_conflicts(
            source_records, destination_user
        )
        orders_to_transfer = self._verified_orders(source_user, to_transfer)
        paid_course_runs_to_transfer = list(
            PaidCourseRun.objects.filter(user=source_user, order__in=orders_to_transfer)
        )

        with transaction.atomic():
            transfer_counts = self._transfer_records(
                to_transfer,
                orders_to_transfer,
                paid_course_runs_to_transfer,
                destination_user,
            )

        self._print_result(
            source_user, destination_user, transfer_counts, skipped_records
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

        Course run enrollments are restricted to verified (paid) enrollments
        for course runs that have already ended - audit enrollments and
        in-progress/self-paced (no end_date) runs are excluded outright, not
        just filtered later. Grades/certificates for course runs use the
        same ended-run filter. Program enrollments/certificates aren't tied
        to a single course run, so they're loaded unconditionally - no mode
        or end-date filter applies to them.
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
                    user=source_user,
                    enrollment_mode__in=EDX_ENROLLMENTS_PAID_MODES,
                    **ended_run,
                ).select_related("run")
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
            "program_enrollments": list(
                ProgramEnrollment.all_objects.filter(user=source_user).select_related(
                    "program"
                )
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

        Returns (to_transfer, skipped_records) - both dicts of label ->
        list of records, so the caller can report exactly which course
        run/program each skip was for.
        """
        conflicting_run_ids = set(
            CourseRunEnrollment.all_objects.filter(user=destination_user).values_list(
                "run_id", flat=True
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
        conflicting_program_ids = set(
            ProgramEnrollment.all_objects.filter(user=destination_user).values_list(
                "program_id", flat=True
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
            "program_enrollments": [
                enrollment
                for enrollment in source_records["program_enrollments"]
                if enrollment.program_id not in conflicting_program_ids
            ],
            "program_certificates": [
                certificate
                for certificate in source_records["program_certificates"]
                if certificate.program_id not in conflicting_cert_program_ids
            ],
        }
        skipped_records = {
            "course_run_enrollments": [
                enrollment
                for enrollment in source_records["course_run_enrollments"]
                if enrollment.run_id in conflicting_run_ids
            ],
            "course_run_grades": [
                grade
                for grade in source_records["course_run_grades"]
                if grade.course_run_id in conflicting_graded_run_ids
            ],
            "course_run_certificates": [
                certificate
                for certificate in source_records["course_run_certificates"]
                if certificate.course_run_id in conflicting_cert_run_ids
            ],
            "program_enrollments": [
                enrollment
                for enrollment in source_records["program_enrollments"]
                if enrollment.program_id in conflicting_program_ids
            ],
            "program_certificates": [
                certificate
                for certificate in source_records["program_certificates"]
                if certificate.program_id in conflicting_cert_program_ids
            ],
        }
        return to_transfer, skipped_records

    def _verified_orders(self, source_user, to_transfer):
        """
        Find the FULFILLED ecommerce Order(s) backing the verified course
        run enrollments that are actually transferring (every enrollment
        loaded here is already verified+ended - _load_source_records only
        loads those - so this just needs the ones that survived the
        duplicate-skip in _partition_conflicts).

        A pending/canceled/declined/errored/refunded order for the same
        course run is left with the source user.

        Note: if an order bundles a Line for something NOT being transferred
        alongside a Line for something that is, the whole order still moves
        with the enrollment - Orders aren't split by line.
        """
        run_ids = [
            enrollment.run_id for enrollment in to_transfer["course_run_enrollments"]
        ]
        if not run_ids:
            return []

        course_run_content_type = ContentType.objects.get(
            app_label="courses", model="courserun"
        )

        return list(
            Order.objects.filter(
                purchaser=source_user,
                state=OrderStatus.FULFILLED,
                lines__purchased_content_type=course_run_content_type,
                lines__purchased_object_id__in=run_ids,
            ).distinct()
        )

    def _transfer_records(
        self,
        to_transfer,
        orders_to_transfer,
        paid_course_runs_to_transfer,
        destination_user,
    ):
        """Transfer each record set and return counts by label."""
        for enrollment in to_transfer["course_run_enrollments"]:
            enrollment.user = destination_user
            enrollment.save_and_log(None)

        for grade in to_transfer["course_run_grades"]:
            grade.user = destination_user
            grade.save_and_log(None)

        for certificate in to_transfer["course_run_certificates"]:
            certificate.user = destination_user
            certificate.save(update_fields=["user"])

        for enrollment in to_transfer["program_enrollments"]:
            enrollment.user = destination_user
            enrollment.save_and_log(None)

        for certificate in to_transfer["program_certificates"]:
            certificate.user = destination_user
            certificate.save(update_fields=["user"])

        for order in orders_to_transfer:
            order.purchaser = destination_user
            order.save(update_fields=["purchaser"])

        for paid_course_run in paid_course_runs_to_transfer:
            paid_course_run.user = destination_user
            paid_course_run.save(update_fields=["user"])

        counts = {label: len(records) for label, records in to_transfer.items()}
        counts["orders"] = len(orders_to_transfer)
        counts["paid_course_runs"] = len(paid_course_runs_to_transfer)
        return counts

    def _print_result(
        self, source_user, destination_user, transfer_counts, skipped_records
    ):
        """
        Print a summary of what was transferred and what was skipped - each
        skipped record is listed by its course run's courseware_id or
        program's readable_id, so it's clear exactly which ones need a
        human to look at, not just how many.
        """
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
        if any(skipped_records.values()):
            self.stdout.write(
                self.style.WARNING(
                    "Skipped (destination already has a matching record): "
                    + ", ".join(
                        f"{label}={len(records)}"
                        for label, records in skipped_records.items()
                        if records
                    )
                )
            )
            for label, records in skipped_records.items():
                if not records:
                    continue
                get_identifier = _SKIPPED_RECORD_IDENTIFIER[label]
                identifiers = ", ".join(get_identifier(record) for record in records)
                self.stdout.write(self.style.WARNING(f"  {label}: {identifiers}"))
