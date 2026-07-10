"""Backfill missing B2B program enrollments.

Users who enrolled in a B2B course run before the automatic program-enrollment
forward fix (b2b.api._enroll_in_program_for_b2b) may be missing the
ProgramEnrollment that should accompany their course enrollment.

This command finds those users and enrolls them in the appropriate program,
mirroring the forward fix exactly (same validation against the contract and the
same courses.api.create_program_enrollments helper, which is idempotent and
writes an audit row).

Only *unambiguous* cases are backfilled: the enrolled course must map to exactly
one program within the run's contract. Ambiguous cases (course belongs to two or
more programs in the same contract) are reported and skipped for manual review.
"""

import logging

from django.core.management import BaseCommand
from django.db.models import Q

from courses.api import create_program_enrollments
from courses.models import CourseRunEnrollment, Program, ProgramEnrollment
from openedx.constants import EDX_ENROLLMENT_VERIFIED_MODE

log = logging.getLogger(__name__)


class Command(BaseCommand):
    """Backfill missing B2B program enrollments."""

    help = """Backfill missing B2B program enrollments.

For each active B2B course-run enrollment, ensure the user is also enrolled in
the program the course belongs to within that run's contract. Only unambiguous
matches (course in exactly one contract program) are backfilled; ambiguous
matches are reported and skipped."""

    def add_arguments(self, parser):
        """Add command line arguments."""

        parser.add_argument(
            "--user", type=str, help="Limit to the specified username or email."
        )
        parser.add_argument(
            "--commit",
            action="store_true",
            default=False,
            help=(
                "Commit changes. Otherwise, this will produce output but won't "
                "make any changes."
            ),
        )

    def handle(self, *args, **kwargs):  # noqa: ARG002
        """Perform the backfill."""

        specific_user = kwargs.pop("user", None)
        commit = kwargs.pop("commit", False)

        if not commit:
            self.stdout.write(
                self.style.WARNING("Commit flag not set - no changes will be made.")
            )

        enrollments = (
            CourseRunEnrollment.objects.filter(run__b2b_contract__isnull=False)
            .select_related("user", "run", "run__course", "run__b2b_contract")
        )

        if specific_user:
            enrollments = enrollments.filter(
                Q(user__email=specific_user) | Q(user__username=specific_user)
            )

        created_count = 0
        already_enrolled = 0
        no_program = 0
        ambiguous = []

        self.stdout.write(
            f"Scanning {enrollments.count()} active B2B course-run enrollment(s)..."
        )

        for enrollment in enrollments:
            user = enrollment.user
            contract = enrollment.run.b2b_contract
            course = enrollment.run.course

            # Programs attached to this contract that also contain this course.
            contract_program_ids = contract.contract_programs.values_list(
                "program_id", flat=True
            )
            candidate_programs = list(
                Program.objects.filter(id__in=contract_program_ids)
                .filter(all_requirements__course=course)
                .distinct()
            )

            if not candidate_programs:
                no_program += 1
                continue

            if len(candidate_programs) > 1:
                ambiguous.append((user, course, contract, candidate_programs))
                continue

            program = candidate_programs[0]

            if ProgramEnrollment.all_objects.filter(
                user=user, program=program
            ).exists():
                already_enrolled += 1
                continue

            self.stdout.write(
                f"\t{user.email}: enrolling in program {program.readable_id} "
                f"(via course {course.readable_id}, contract {contract})"
            )

            if commit:
                create_program_enrollments(
                    user, [program], enrollment_mode=EDX_ENROLLMENT_VERIFIED_MODE
                )
            created_count += 1

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"{'Created' if commit else 'Would create'} {created_count} "
                "program enrollment(s)."
            )
        )
        self.stdout.write(f"Already enrolled (skipped): {already_enrolled}")
        self.stdout.write(f"No matching program (skipped): {no_program}")
        self.stdout.write(
            f"Ambiguous - course in 2+ contract programs (skipped): {len(ambiguous)}"
        )

        if ambiguous:
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING("Ambiguous cases needing manual review:")
            )
            for user, course, contract, programs in ambiguous:
                program_ids = ", ".join(p.readable_id for p in programs)
                self.stdout.write(
                    f"\t{user.email}: course {course.readable_id} in "
                    f"contract {contract} maps to programs [{program_ids}]"
                )
