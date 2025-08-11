"""
Management command to sync dates and title for all or a specific course run from edX
"""

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from mitol.common.utils.datetime import now_in_utc

from courses.api import sync_course_runs
from courses.models import CourseRun


class Command(BaseCommand):
    """
    Command to sync course run dates and title from edX.
    """

    help = "Sync dates and title for all or a specific course run from edX."

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            "--run",
            type=str,
            help="The 'courseware_id' value for a CourseRun to sync",
        )
        group.add_argument(
            "--all",
            type=bool,
            help="Sync all CourseRuns",
        )
        super().add_arguments(parser)

    def handle(self, *args, **options):  # pylint: disable=too-many-locals  # noqa: ARG002
        """Handle command execution"""
        runs = []
        if options["run"]:
            try:
                runs = [CourseRun.objects.get(courseware_id=options["run"])]
            except CourseRun.DoesNotExist:
                raise CommandError(  # noqa: B904
                    "Could not find run with courseware_id={}".format(options["run"])  # noqa: EM103
                )
        elif options["all"]:
            # We pick up all the course runs that do not have an expiration date (implies not having
            # an end_date) or those that are not expired yet, in case the user has not specified any
            # course run id.
            now = now_in_utc()
            runs = CourseRun.objects.live().filter(
                Q(expiration_date__isnull=True) | Q(expiration_date__gt=now)
            )

        success_count, error_count = sync_course_runs(runs)

        self.stdout.write(
            self.style.SUCCESS(
                f"Sync complete: {success_count} updated, {error_count} failures"
            )
        )
