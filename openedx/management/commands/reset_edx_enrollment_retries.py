"""
Management command to reset the edX enrollment repair retry counter for a
set of enrollments, e.g. after fixing a course misconfiguration that caused
a wave of enrollments to exhaust their automatic repair retries.
"""

from django.core.management import BaseCommand

from courses.models import CourseRunEnrollment
from openedx.constants import OPENEDX_ENROLLMENT_REPAIR_MAX_RETRIES
from users.api import fetch_users


class Command(BaseCommand):
    """
    Management command to reset edx_enrollment_retry_count so enrollments
    become eligible for automatic repair again.
    """

    help = (
        "Resets edx_enrollment_retry_count to 0 for enrollments matching the "
        "given filters, so they're picked up again by the scheduled edX "
        "enrollment repair task instead of staying dead-lettered."
    )

    def add_arguments(self, parser):
        """
        Definition of arguments this command accepts
        """
        parser.add_argument(
            "--run", type=str, help="The 'courseware_id' value for a target CourseRun"
        )
        parser.add_argument(
            "--only-exhausted",
            action="store_true",
            help=(
                "Only reset enrollments that have actually exhausted their "
                "retries, instead of every matching enrollment"
            ),
        )
        parser.add_argument(
            "uservalues",
            nargs="*",
            type=str,
            help=(
                "The ids, emails, or usernames of the target Users (all values will be assumed "
                "to be of the same type as the first)"
            ),
        )

    def handle(self, *args, **options):  # noqa: ARG002
        """Run the command"""
        enrollment_filter = {"edx_enrolled": False}
        if options["run"]:
            enrollment_filter["run__courseware_id"] = options["run"]
        if options["uservalues"]:
            enrollment_filter["user__in"] = fetch_users(options["uservalues"])
        if options["only_exhausted"]:
            enrollment_filter["edx_enrollment_retry_count__gte"] = (
                OPENEDX_ENROLLMENT_REPAIR_MAX_RETRIES
            )

        updated = CourseRunEnrollment.objects.filter(**enrollment_filter).update(
            edx_enrollment_retry_count=0
        )

        if updated == 0:
            self.stderr.write(
                self.style.ERROR(
                    f"No course run enrollments found that match the given filters ({enrollment_filter}).\nExiting..."
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Reset edX enrollment repair retry count for {updated} enrollment(s)."
            )
        )
