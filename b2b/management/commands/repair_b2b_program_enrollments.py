"""Check and repair B2B program enrollments."""

import logging

from django.core.management import BaseCommand
from django.db.models import Q

from b2b.models import ContractProgramItem
from courses.constants import ENROLL_CHANGE_STATUS_UNENROLLED
from courses.models import Program, ProgramEnrollment

log = logging.getLogger(__name__)


class Command(BaseCommand):
    """Check and repair B2B program enrollments."""

    help = """Check and repair B2B program enrollments.

Unenroll users from B2B programs that belong to contracts that the user doesn't have an attachment for."""

    def add_arguments(self, parser):
        """Add command line arguments."""

        parser.add_argument(
            "--user", type=str, help="Check specified username or email."
        )
        parser.add_argument(
            "--commit",
            action="store_true",
            default=False,
            help="Commit changes. Otherwise, this will produce output but won't make any changes.",
        )

    def handle(self, *args, **kwargs):  # noqa: ARG002
        """Perform check and repair operation."""

        specific_user = kwargs.pop("user", None)
        commit = kwargs.pop("commit", False)

        if not commit:
            self.stdout.write(
                self.style.WARNING("Commit flag not set - no changes will be made.")
            )

        b2b_programs = Program.objects.filter(
            b2b_only=True,
            contract_memberships__isnull=False,
        ).distinct()

        for program in b2b_programs:
            program_contract_ids = ContractProgramItem.objects.filter(
                program=program
            ).values_list("contract_id", flat=True)

            extraneous_enrollments = (
                ProgramEnrollment.objects.filter(program=program)
                .exclude(user__b2b_contracts__in=program_contract_ids)
                .select_related("user", "program")
                .distinct()
            )

            if specific_user:
                extraneous_enrollments = extraneous_enrollments.filter(
                    Q(user__email=specific_user) | Q(user__username=specific_user)
                )

            count = extraneous_enrollments.count()
            if count > 0:
                self.stdout.write(
                    f"Program {program.readable_id}: unenrolling {count} user(s):"
                )

                for enrollment in extraneous_enrollments:
                    self.stdout.write(f"\t{enrollment.user.email}")
                    if commit:
                        enrollment.deactivate_and_save(
                            ENROLL_CHANGE_STATUS_UNENROLLED, no_user=True
                        )

                self.stdout.write("\n")
