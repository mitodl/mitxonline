"""Transfer course-related user records from one user to another."""

from argparse import RawTextHelpFormatter

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from courses.constants import PROGRAM_ENROLLMENT_UPGRADE_MODE
from courses.models import (
    Course,
    CourseRun,
    CourseRunCertificate,
    CourseRunEnrollment,
    CourseRunGrade,
    PaidCourseRun,
    Program,
    ProgramCertificate,
    ProgramEnrollment,
)
from ecommerce.models import DiscountRedemption, Order, OrderStatus, RefundRequest
from flexiblepricing.models import FlexiblePrice
from openedx.api import enroll_in_edx_course_runs
from openedx.constants import EDX_ENROLLMENTS_PAID_MODES
from users.api import fetch_user

User = get_user_model()

# Course runs whose courseware_id contains this get an edX enrollment created
# for the destination user after their enrollment is transferred.
EDX_SYNC_COURSEWARE_ID_MARKER = "MITxT"


class Command(BaseCommand):
    """
    Transfer course-related records between two users.

    Moves, for the source user, unconditionally - in any enrollment mode
    (verified or audit) and whether or not the course run has ended:
    - Course run enrollments, grades and certificates.
    - Program enrollments and certificates.
    - The FULFILLED Order(s) backing each verified course run or program
      enrollment that transfers, so the payment record - and the "already
      paid for this" check it drives - follows the enrollment instead of
      staying attributed to the source user. With each order go its
      PaidCourseRun records, discount redemptions and refund requests (its
      lines and transactions belong to the order), and the source user's
      flexible price (financial assistance) request for each course or
      program the order bought.

    A record is skipped, not aborted, if the destination user already has a
    matching enrollment/grade/certificate/flexible price; transferred and
    skipped counts are reported at the end.

    After the transfer commits, each transferred active enrollment for a
    course run whose courseware_id contains "MITxT" is also created in edX
    for the destination user, in the same mode. An enrollment the destination
    user already had in mitxonline is reported and skipped, and edX errors are
    reported per course run without undoing the transfer.

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
        orders_to_transfer = self._verified_orders(source_user, to_transfer)
        order_records, order_skipped_counts = self._order_records(
            source_user, destination_user, orders_to_transfer
        )
        skipped_counts.update(order_skipped_counts)

        with transaction.atomic():
            transfer_counts = self._transfer_records(
                to_transfer,
                orders_to_transfer,
                order_records,
                destination_user,
            )

        self._print_result(
            source_user, destination_user, transfer_counts, skipped_counts
        )
        self._sync_edx_enrollments(
            destination_user,
            to_transfer["course_run_enrollments"],
            source_records["course_run_enrollments"],
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

        Every record is loaded unconditionally - no enrollment mode or
        course run end-date filter applies.
        """
        return {
            "course_run_enrollments": list(
                CourseRunEnrollment.all_objects.filter(user=source_user).select_related(
                    "run"
                )
            ),
            "course_run_grades": list(
                CourseRunGrade.objects.filter(user=source_user).select_related(
                    "course_run"
                )
            ),
            "course_run_certificates": list(
                CourseRunCertificate.all_objects.filter(
                    user=source_user
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

        Returns (to_transfer, skipped_counts).
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
        skipped_counts = {
            label: len(source_records[label]) - len(to_transfer[label])
            for label in source_records
        }
        return to_transfer, skipped_counts

    def _verified_orders(self, source_user, to_transfer):
        """
        Find the FULFILLED ecommerce Order(s) backing the verified (paid)
        course run and program enrollments that are actually transferring -
        i.e. the ones that survived the duplicate-skip in
        _partition_conflicts. Audit enrollments transfer without moving any
        order.

        A pending/canceled/declined/errored/refunded order for the same
        course run or program is left with the source user.

        Note: if an order bundles a Line for something NOT being transferred
        alongside a Line for something that is, the whole order still moves
        with the enrollment - Orders aren't split by line.
        """
        run_ids = [
            enrollment.run_id
            for enrollment in to_transfer["course_run_enrollments"]
            if enrollment.enrollment_mode in EDX_ENROLLMENTS_PAID_MODES
        ]
        program_ids = [
            enrollment.program_id
            for enrollment in to_transfer["program_enrollments"]
            if enrollment.enrollment_mode == PROGRAM_ENROLLMENT_UPGRADE_MODE
        ]
        if not run_ids and not program_ids:
            return []

        content_types = ContentType.objects.get_for_models(CourseRun, Program)
        return list(
            Order.objects.filter(
                Q(
                    lines__purchased_content_type=content_types[CourseRun],
                    lines__purchased_object_id__in=run_ids,
                )
                | Q(
                    lines__purchased_content_type=content_types[Program],
                    lines__purchased_object_id__in=program_ids,
                ),
                purchaser=source_user,
                state=OrderStatus.FULFILLED,
            ).distinct()
        )

    def _order_records(self, source_user, destination_user, orders):
        """
        Load the source user's records tied to the transferring orders: their
        PaidCourseRuns, discount redemptions and refund requests, and the
        flexible price for each course or program the orders bought.

        A flexible price is skipped if the destination user already has one
        for the same course or program (one per user per courseware object).

        Returns (order_records, skipped_counts).
        """
        if not orders:
            return {
                "paid_course_runs": [],
                "discount_redemptions": [],
                "refund_requests": [],
                "flexible_prices": [],
            }, {}

        content_types = ContentType.objects.get_for_models(CourseRun, Program, Course)
        lines = [line for order in orders for line in order.lines.all()]
        course_ids = set(
            CourseRun.objects.filter(
                id__in=[
                    line.purchased_object_id
                    for line in lines
                    if line.purchased_content_type_id == content_types[CourseRun].id
                ]
            ).values_list("course_id", flat=True)
        )
        program_ids = {
            line.purchased_object_id
            for line in lines
            if line.purchased_content_type_id == content_types[Program].id
        }
        courseware_filter = Q(
            courseware_content_type=content_types[Course],
            courseware_object_id__in=course_ids,
        ) | Q(
            courseware_content_type=content_types[Program],
            courseware_object_id__in=program_ids,
        )
        flexible_prices = list(
            FlexiblePrice.objects.filter(courseware_filter, user=source_user)
        )
        destination_courseware = set(
            FlexiblePrice.objects.filter(
                courseware_filter, user=destination_user
            ).values_list("courseware_content_type_id", "courseware_object_id")
        )
        flexible_prices_to_transfer = [
            flexible_price
            for flexible_price in flexible_prices
            if (
                flexible_price.courseware_content_type_id,
                flexible_price.courseware_object_id,
            )
            not in destination_courseware
        ]

        order_records = {
            "paid_course_runs": list(
                PaidCourseRun.objects.filter(user=source_user, order__in=orders)
            ),
            "discount_redemptions": list(
                DiscountRedemption.objects.filter(
                    redeemed_by=source_user, redeemed_order__in=orders
                )
            ),
            "refund_requests": list(
                RefundRequest.objects.filter(user=source_user, order__in=orders)
            ),
            "flexible_prices": flexible_prices_to_transfer,
        }
        skipped_counts = {
            "flexible_prices": len(flexible_prices) - len(flexible_prices_to_transfer)
        }
        return order_records, skipped_counts

    def _transfer_records(
        self,
        to_transfer,
        orders_to_transfer,
        order_records,
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

        self._transfer_order_records(
            orders_to_transfer, order_records, destination_user
        )

        counts = {label: len(records) for label, records in to_transfer.items()}
        counts["orders"] = len(orders_to_transfer)
        counts.update({label: len(records) for label, records in order_records.items()})
        return counts

    def _transfer_order_records(self, orders, order_records, destination_user):
        """Move the orders and their related records to the destination user."""
        for records, user_field in (
            (orders, "purchaser"),
            (order_records["paid_course_runs"], "user"),
            (order_records["discount_redemptions"], "redeemed_by"),
            (order_records["refund_requests"], "user"),
            (order_records["flexible_prices"], "user"),
        ):
            for record in records:
                setattr(record, user_field, destination_user)
                record.save(update_fields=[user_field])

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

    def _sync_edx_enrollments(
        self, destination_user, transferred_enrollments, source_enrollments
    ):
        """
        Create edX enrollments for the destination user for transferred
        enrollments in "MITxT" course runs. Enrollments skipped as duplicates
        in mitxonline and inactive enrollments are reported and skipped. Any
        edX error is reported and the next course run is tried.
        """
        transferred_ids = {enrollment.id for enrollment in transferred_enrollments}
        for enrollment in source_enrollments:
            courseware_id = enrollment.run.courseware_id
            if EDX_SYNC_COURSEWARE_ID_MARKER not in courseware_id:
                continue
            if enrollment.id not in transferred_ids:
                self.stdout.write(
                    f"{destination_user.email} already has an enrollment in "
                    f"{courseware_id}, skipping edX sync."
                )
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
