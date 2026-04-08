"""Upgrade program enrollments that are eligible for verified mode."""

from django.core.management.base import BaseCommand

from courses.api import upgrade_program_enrollment_if_eligible
from courses.models import ProgramEnrollment
from openedx.constants import EDX_ENROLLMENT_AUDIT_MODE


class Command(BaseCommand):
    """Iterate through all program enrollments and upgrade eligible ones."""

    help = "Upgrade all eligible program enrollments to verified mode"

    def handle(self, *args, **options):  # pylint: disable=unused-argument  # noqa: ARG002
        processed_count = 0
        upgraded_count = 0

        for program_enrollment in ProgramEnrollment.objects.filter(
            enrollment_mode=EDX_ENROLLMENT_AUDIT_MODE
        ):
            _, upgraded = upgrade_program_enrollment_if_eligible(program_enrollment)

            if upgraded:
                upgraded_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Upgraded enrollment for user {program_enrollment.user.username}."
                    )
                )
            processed_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Processed "
                f"{processed_count} program enrollments; "
                f"upgraded {upgraded_count}."
            )
        )
