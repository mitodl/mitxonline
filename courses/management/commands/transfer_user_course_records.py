"""Transfer course-related user records from one user to another."""

from argparse import RawTextHelpFormatter
from collections import Counter

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from courses.models import (
    CourseRunCertificate,
    CourseRunEnrollment,
    CourseRunGrade,
    PaidCourseRun,
    PaidProgram,
    ProgramCertificate,
    ProgramEnrollment,
)
from ecommerce.models import DiscountRedemption, Order, RefundRequest
from flexiblepricing.constants import FlexiblePriceStatus
from flexiblepricing.models import FlexiblePrice
from openedx.api import enroll_in_edx_course_runs
from openedx.constants import EDX_ENROLLMENTS_PAID_MODES
from users.api import fetch_user

User = get_user_model()

# Course runs whose courseware_id contains this get an edX enrollment created
# for the destination user after their enrollment is transferred.
EDX_SYNC_COURSEWARE_ID_MARKER = "MITxT"

APPROVED_FLEXIBLE_PRICE_STATUSES = (
    FlexiblePriceStatus.APPROVED,
    FlexiblePriceStatus.AUTO_APPROVED,
)

# label -> (model manager, field pointing at the user)
RECORD_TYPES = {
    "course_run_enrollments": (CourseRunEnrollment.all_objects, "user"),
    "course_run_grades": (CourseRunGrade.objects, "user"),
    "course_run_certificates": (CourseRunCertificate.all_objects, "user"),
    "program_enrollments": (ProgramEnrollment.all_objects, "user"),
    "program_certificates": (ProgramCertificate.all_objects, "user"),
    "orders": (Order.objects, "purchaser"),
    "paid_course_runs": (PaidCourseRun.objects, "user"),
    "paid_programs": (PaidProgram.objects, "user"),
    "discount_redemptions": (DiscountRedemption.objects, "redeemed_by"),
    "refund_requests": (RefundRequest.objects, "user"),
    "flexible_prices": (FlexiblePrice.objects, "user"),
}

# Record types that are unique per user, keyed by the field(s) that
# uniqueness is defined on alongside the user.
UNIQUE_KEYS = {
    "course_run_enrollments": lambda record: record.run_id,
    "course_run_grades": lambda record: record.course_run_id,
    "course_run_certificates": lambda record: record.course_run_id,
    "program_enrollments": lambda record: record.program_id,
    "program_certificates": lambda record: record.program_id,
    "flexible_prices": lambda record: (
        record.courseware_content_type_id,
        record.courseware_object_id,
    ),
}


class Command(BaseCommand):
    """
    Transfer every course-related record from one user to another.

    Moves all of the source user's records, unconditionally - any enrollment
    mode, any order state, whether or not the course run has ended:
    - Course run enrollments, grades and certificates.
    - Program enrollments and certificates.
    - Orders (with their lines and transactions), PaidCourseRun and
      PaidProgram records, discount redemptions, refund requests and
      flexible price (financial assistance) requests.

    Where the destination user already has a record that only one user can
    have per course run/program/course, the two are merged into one record
    owned by the destination user and the source's duplicate is deleted:
    - Enrollments: the destination's enrollment is kept, upgraded to the
      source's paid mode and/or reactivated if the source's was active.
    - Grades: the destination's grade takes the source's values if the
      source's is better (passed beats not passed, then the higher grade).
    - Certificates: the source's certificate replaces the destination's if
      the destination's is revoked and the source's isn't.
    - Flexible prices: the source's replaces the destination's if the
      source's is approved and the destination's isn't.

    After the transfer commits, each active enrollment in a course run whose
    courseware_id contains "MITxT" that was transferred, or that was changed
    by a merge, is created in edX for the destination user in its mode. edX
    errors are reported per course run without undoing the transfer.

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

        with transaction.atomic():
            transfer_counts, merge_counts, edx_sync_enrollments = (
                self._transfer_records(source_user, destination_user)
            )

        self._print_result(source_user, destination_user, transfer_counts, merge_counts)
        self._sync_edx_enrollments(destination_user, edx_sync_enrollments)

    def _fetch_user(self, email, option_name):
        """Look up a user by email and normalize fetch errors to CommandError."""
        try:
            return fetch_user(email)
        except User.DoesNotExist as exc:
            msg = f"Could not find user for --{option_name}={email}."
            raise CommandError(msg) from exc

    def _load_records(self, user):
        """Load every transferable record for a user, by label."""
        return {
            label: list(manager.filter(**{user_field: user}))
            for label, (manager, user_field) in RECORD_TYPES.items()
        }

    def _transfer_records(self, source_user, destination_user):
        """
        Move each of the source user's records to the destination user, merging
        it into the destination's matching record where one exists.

        Returns (transfer_counts, merge_counts, edx_sync_enrollments), where
        edx_sync_enrollments are the destination user's course run enrollments
        that were transferred or changed by a merge.
        """
        source_records = self._load_records(source_user)
        destination_records = self._load_records(destination_user)
        transfer_counts = Counter(dict.fromkeys(RECORD_TYPES, 0))
        merge_counts = Counter()
        edx_sync_enrollments = []

        for label, records in source_records.items():
            key = UNIQUE_KEYS.get(label)
            existing = (
                {key(record): record for record in destination_records[label]}
                if key
                else {}
            )
            for record in records:
                destination_record = existing.get(key(record)) if key else None
                if destination_record is None:
                    self._move(label, record, destination_user)
                    transfer_counts[label] += 1
                    synced_enrollment = record
                else:
                    changed = self._merge(
                        label, record, destination_record, destination_user
                    )
                    merge_counts[label] += 1
                    synced_enrollment = destination_record if changed else None
                if label == "course_run_enrollments" and synced_enrollment:
                    edx_sync_enrollments.append(synced_enrollment)

        return transfer_counts, merge_counts, edx_sync_enrollments

    def _move(self, label, record, destination_user):
        """Reassign a record to the destination user."""
        user_field = RECORD_TYPES[label][1]
        setattr(record, user_field, destination_user)
        if hasattr(record, "save_and_log"):
            record.save_and_log(None)
        else:
            record.save(update_fields=[user_field])

    def _merge(self, label, source_record, destination_record, destination_user):
        """
        Merge a source record into the destination user's matching record,
        leaving one record owned by the destination user. Returns True if the
        destination user's record changed.
        """
        if label in ("course_run_enrollments", "program_enrollments"):
            return self._merge_enrollment(source_record, destination_record)
        if label == "course_run_grades":
            return self._merge_grade(source_record, destination_record)
        if label in ("course_run_certificates", "program_certificates"):
            source_is_better = (
                destination_record.is_revoked and not source_record.is_revoked
            )
        else:  # flexible_prices
            source_is_better = (
                source_record.status in APPROVED_FLEXIBLE_PRICE_STATUSES
                and destination_record.status not in APPROVED_FLEXIBLE_PRICE_STATUSES
            )
        if source_is_better:
            destination_record.delete()
            self._move(label, source_record, destination_user)
        else:
            source_record.delete()
        return source_is_better

    def _merge_enrollment(self, source_enrollment, destination_enrollment):
        """
        Upgrade the destination's enrollment to the source's paid mode and
        reactivate it if the source's is active, then delete the source's.
        """
        changed = False
        if (
            source_enrollment.enrollment_mode in EDX_ENROLLMENTS_PAID_MODES
            and destination_enrollment.enrollment_mode not in EDX_ENROLLMENTS_PAID_MODES
        ):
            destination_enrollment.enrollment_mode = source_enrollment.enrollment_mode
            changed = True
        if source_enrollment.active and not destination_enrollment.active:
            destination_enrollment.active = True
            destination_enrollment.change_status = None
            changed = True
        if changed:
            destination_enrollment.save_and_log(None)
        source_enrollment.delete()
        return changed

    def _merge_grade(self, source_grade, destination_grade):
        """
        Copy the source's grade onto the destination's if it's better, then
        delete the source's.
        """
        changed = (source_grade.passed, source_grade.grade) > (
            destination_grade.passed,
            destination_grade.grade,
        )
        if changed:
            for field in ("grade", "letter_grade", "passed", "set_by_admin"):
                setattr(destination_grade, field, getattr(source_grade, field))
            destination_grade.save_and_log(None)
        source_grade.delete()
        return changed

    def _print_result(
        self, source_user, destination_user, transfer_counts, merge_counts
    ):
        """Print a summary of what was transferred and what was merged."""
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
        if merge_counts:
            self.stdout.write(
                self.style.WARNING(
                    "Merged into the destination's existing record: "
                    + ", ".join(
                        f"{label}={count}" for label, count in merge_counts.items()
                    )
                )
            )

    def _sync_edx_enrollments(self, destination_user, enrollments):
        """
        Create edX enrollments for the destination user for transferred or
        merged enrollments in "MITxT" course runs. Inactive enrollments are
        reported and skipped. Any edX error is reported and the next course
        run is tried.
        """
        for enrollment in enrollments:
            courseware_id = enrollment.run.courseware_id
            if EDX_SYNC_COURSEWARE_ID_MARKER not in courseware_id:
                continue
            if not enrollment.active:
                self.stdout.write(
                    f"Enrollment in {courseware_id} is inactive "
                    f"(change_status={enrollment.change_status}), skipping edX sync."
                )
                continue
            try:
                enroll_in_edx_course_runs(
                    destination_user,
                    [enrollment.run],
                    mode=enrollment.enrollment_mode,
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created edX enrollment for {destination_user.email} "
                        f"in {courseware_id} (mode={enrollment.enrollment_mode})."
                    )
                )
                if not enrollment.edx_enrolled:
                    enrollment.edx_enrolled = True
                    enrollment.save(update_fields=["edx_enrolled"])
            except Exception as exc:  # noqa: BLE001
                self.stdout.write(
                    self.style.ERROR(
                        f"Could not create edX enrollment for {destination_user.email} "
                        f"in {courseware_id}: {exc}"
                    )
                )
