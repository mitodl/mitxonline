"""
Report upgraded program enrollments with no purchase or B2B contract behind them.

An upgraded program enrollment entitles the learner to verified course run
enrollments in the program. Before hq#14063 the nightly auto-upgrade task also
upgraded learners who had collected enough verified run enrollments on their
own, and the 0112 migration carried those over as upgraded. This lists them so
they can be reviewed; it changes nothing.

An enrollment counts as backed when the learner has a fulfilled order for the
program (PaidProgram), the enrollment is tied to a B2B contract, or the learner
belongs to a B2B contract that includes the program.
"""

import csv
from collections import Counter

from django.core.management.base import BaseCommand
from django.db.models import Exists, OuterRef

from b2b.models import UserB2BContract
from courses.constants import PROGRAM_ENROLLMENT_UPGRADE_MODE
from courses.models import PaidProgram, ProgramCertificate, ProgramEnrollment
from ecommerce.models import OrderStatus


def get_unpurchased_upgraded_program_enrollments():
    """
    Return upgraded program enrollments with no purchase or B2B contract behind them.

    Returns:
        QuerySet[ProgramEnrollment]: annotated with has_program_cert
    """
    paid_program = PaidProgram.objects.filter(
        user_id=OuterRef("user_id"),
        program_id=OuterRef("program_id"),
        order__state=OrderStatus.FULFILLED,
    )
    contract_with_program = UserB2BContract.objects.filter(
        user_id=OuterRef("user_id"),
        contract_page__contract_programs__program_id=OuterRef("program_id"),
    )
    program_cert = ProgramCertificate.all_objects.filter(
        user_id=OuterRef("user_id"),
        program_id=OuterRef("program_id"),
        is_revoked=False,
    )

    return (
        ProgramEnrollment.all_objects.filter(
            enrollment_mode=PROGRAM_ENROLLMENT_UPGRADE_MODE,
            b2b_contract__isnull=True,
        )
        .exclude(Exists(paid_program))
        .exclude(Exists(contract_with_program))
        .annotate(has_program_cert=Exists(program_cert))
        .select_related("program")
        .order_by("program__readable_id", "id")
    )


class Command(BaseCommand):
    """Report upgraded program enrollments with no purchase or B2B contract behind them."""

    help = __doc__

    def add_arguments(self, parser):
        """Add the --list argument."""
        parser.add_argument(
            "--list",
            action="store_true",
            help="Also print one CSV row per enrollment (ids only, no learner PII).",
        )
        super().add_arguments(parser)

    def handle(self, *args, **options):  # noqa: ARG002
        """Print per-program counts, and optionally the enrollments themselves."""
        enrollments = get_unpurchased_upgraded_program_enrollments()

        per_program = Counter()
        writer = None
        if options["list"]:
            writer = csv.writer(self.stdout)
            writer.writerow(
                [
                    "enrollment_id",
                    "user_id",
                    "program",
                    "active",
                    "created_on",
                    "has_program_cert",
                ]
            )

        for enrollment in enrollments.iterator():
            per_program[enrollment.program.readable_id] += 1
            if writer:
                writer.writerow(
                    [
                        enrollment.id,
                        enrollment.user_id,
                        enrollment.program.readable_id,
                        enrollment.active,
                        enrollment.created_on.isoformat(),
                        enrollment.has_program_cert,
                    ]
                )

        self.stdout.write("")
        for readable_id, count in sorted(per_program.items()):
            self.stdout.write(f"{readable_id}: {count}")
        self.stdout.write(
            self.style.SUCCESS(
                f"{sum(per_program.values())} upgraded program enrollments "
                f"across {len(per_program)} programs have no purchase or "
                "B2B contract behind them."
            )
        )
