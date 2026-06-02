"""Transfer course-related user records from one user to another."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

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
    """Transfer course-related records between two users."""

    help = (
        "Transfer course run/program enrollments, grades, and certificates from one "
        "user to another by email."
    )

    def add_arguments(self, parser):
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
            raise CommandError("Source and destination users must be different.")

        source_records = self._load_source_records(source_user)
        self._raise_on_conflicts(source_records, destination_user)

        with transaction.atomic():
            transfer_counts = self._transfer_records(source_records, destination_user)

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

    def _fetch_user(self, email, option_name):
        """Look up a user by email and normalize fetch errors to CommandError."""
        try:
            return fetch_user(email)
        except User.DoesNotExist as exc:
            raise CommandError(
                f"Could not find user for --{option_name}={email}."
            ) from exc

    def _load_source_records(self, source_user):
        """Load all transfer candidates for the source user."""
        return {
            "course_run_enrollments": list(
                CourseRunEnrollment.all_objects.filter(user=source_user).select_related(
                    "run"
                )
            ),
            "program_enrollments": list(
                ProgramEnrollment.all_objects.filter(user=source_user).select_related(
                    "program"
                )
            ),
            "course_run_grades": list(
                CourseRunGrade.objects.filter(user=source_user).select_related(
                    "course_run"
                )
            ),
            "course_run_certificates": list(
                CourseRunCertificate.all_objects.filter(user=source_user).select_related(
                    "course_run"
                )
            ),
            "program_certificates": list(
                ProgramCertificate.all_objects.filter(user=source_user).select_related(
                    "program"
                )
            ),
        }

    def _raise_on_conflicts(self, source_records, destination_user):
        """Abort if the destination already has any overlapping records."""
        conflicts = []

        course_run_ids = [
            enrollment.run_id for enrollment in source_records["course_run_enrollments"]
        ]
        program_ids = [
            enrollment.program_id
            for enrollment in source_records["program_enrollments"]
        ]
        graded_course_run_ids = [
            grade.course_run_id for grade in source_records["course_run_grades"]
        ]
        certificate_course_run_ids = [
            certificate.course_run_id
            for certificate in source_records["course_run_certificates"]
        ]
        certificate_program_ids = [
            certificate.program_id
            for certificate in source_records["program_certificates"]
        ]

        conflicting_course_run_enrollments = list(
            CourseRunEnrollment.all_objects.filter(
                user=destination_user, run_id__in=course_run_ids
            ).select_related("run")
        )
        if conflicting_course_run_enrollments:
            conflicts.append(
                "course run enrollments for {}".format(
                    ", ".join(
                        sorted(
                            {
                                enrollment.run.courseware_id
                                for enrollment in conflicting_course_run_enrollments
                            }
                        )
                    )
                )
            )

        conflicting_program_enrollments = list(
            ProgramEnrollment.all_objects.filter(
                user=destination_user, program_id__in=program_ids
            ).select_related("program")
        )
        if conflicting_program_enrollments:
            conflicts.append(
                "program enrollments for {}".format(
                    ", ".join(
                        sorted(
                            {
                                enrollment.program.readable_id
                                for enrollment in conflicting_program_enrollments
                            }
                        )
                    )
                )
            )

        conflicting_grades = list(
            CourseRunGrade.objects.filter(
                user=destination_user, course_run_id__in=graded_course_run_ids
            ).select_related("course_run")
        )
        if conflicting_grades:
            conflicts.append(
                "course run grades for {}".format(
                    ", ".join(
                        sorted(
                            {grade.course_run.courseware_id for grade in conflicting_grades}
                        )
                    )
                )
            )

        conflicting_course_run_certificates = list(
            CourseRunCertificate.all_objects.filter(
                user=destination_user, course_run_id__in=certificate_course_run_ids
            ).select_related("course_run")
        )
        if conflicting_course_run_certificates:
            conflicts.append(
                "course run certificates for {}".format(
                    ", ".join(
                        sorted(
                            {
                                certificate.course_run.courseware_id
                                for certificate in conflicting_course_run_certificates
                            }
                        )
                    )
                )
            )

        conflicting_program_certificates = list(
            ProgramCertificate.all_objects.filter(
                user=destination_user, program_id__in=certificate_program_ids
            ).select_related("program")
        )
        if conflicting_program_certificates:
            conflicts.append(
                "program certificates for {}".format(
                    ", ".join(
                        sorted(
                            {
                                certificate.program.readable_id
                                for certificate in conflicting_program_certificates
                            }
                        )
                    )
                )
            )

        if conflicts:
            raise CommandError(
                "Transfer aborted because the destination user already has {}.".format(
                    "; ".join(conflicts)
                )
            )

    def _transfer_records(self, source_records, destination_user):
        """Transfer each record set and return counts by label."""
        for enrollment in source_records["course_run_enrollments"]:
            enrollment.user = destination_user
            enrollment.save_and_log(None)

        for enrollment in source_records["program_enrollments"]:
            enrollment.user = destination_user
            enrollment.save_and_log(None)

        for grade in source_records["course_run_grades"]:
            grade.user = destination_user
            grade.save_and_log(None)

        for certificate in source_records["course_run_certificates"]:
            certificate.user = destination_user
            certificate.save(update_fields=["user"])

        for certificate in source_records["program_certificates"]:
            certificate.user = destination_user
            certificate.save(update_fields=["user"])

        return {
            "course_run_enrollments": len(source_records["course_run_enrollments"]),
            "program_enrollments": len(source_records["program_enrollments"]),
            "course_run_grades": len(source_records["course_run_grades"]),
            "course_run_certificates": len(source_records["course_run_certificates"]),
            "program_certificates": len(source_records["program_certificates"]),
        }
