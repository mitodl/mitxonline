"""Check and repair B2B program enrollments."""

import logging

from django.core.management import BaseCommand
from django.db.models import Count, Prefetch, Q

from courses.constants import ENROLL_CHANGE_STATUS_UNENROLLED
from courses.models import ProgramEnrollment
from users.models import User

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

        b2b_program_enrollment_qset = ProgramEnrollment.objects.annotate(
            b2b_program_count=Count("program__contract_memberships")
        ).filter(b2b_program_count__gt=0)

        specific_user = kwargs.pop("user", None)
        commit = kwargs.pop("commit", False)

        if not commit:
            self.stdout.write(
                self.style.WARNING("Commit flag not set - no changes will be made.")
            )

        users = User.objects.prefetch_related(
            Prefetch("programenrollment_set", queryset=b2b_program_enrollment_qset)
        )

        if specific_user:
            users = users.filter(Q(email=specific_user) | Q(username=specific_user))

        for user in users.all():
            extraneous_enrollments = user.programenrollment_set.exclude(
                Q(program__b2b_only=False)
                | Q(
                    program__contract_memberships__contract__in=user.b2b_contracts.all()
                )
            ).all()

            if extraneous_enrollments.count() > 0:
                self.stdout.write(
                    f"Unenrolling user {user.email} from {extraneous_enrollments.count()} program enrollments:"
                )

                for enrollment in extraneous_enrollments:
                    enrollment.deactivate_and_save(
                        ENROLL_CHANGE_STATUS_UNENROLLED, no_user=True
                    ) if commit else None
                    self.stdout.write(f"\t{enrollment.program.readable_id} ")

                self.stdout.write("\n")
