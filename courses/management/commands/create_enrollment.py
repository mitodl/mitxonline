"""Management command to change enrollment status"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from courses.api import create_run_enrollments
from courses.models import CourseRun
from users.api import fetch_user

User = get_user_model()


class Command(BaseCommand):
    """creates an enrollment for a course run"""

    help = "Creates an enrollment for a course run"

    def add_arguments(self, parser):
        parser.add_argument(
            "--user",
            type=str,
            help="The id, email, or username of the User",
            required=True,
        )
        parser.add_argument(
            "--run",
            type=str,
            help="The 'courseware_id' value for the CourseRun",
            required=True,
        )
        parser.add_argument(
            "-k",
            "--keep-failed-enrollments",
            action="store_true",
            dest="keep_failed_enrollments",
            help="If provided, enrollment records will be kept even if edX enrollment fails",
        )
        super().add_arguments(parser)

    def handle(self, *args, **options):  # noqa: ARG002
        """Handle command execution"""
        user = fetch_user(options["user"])

        run = CourseRun.objects.filter(courseware_id=options["run"]).first()
        if run is None:
            raise CommandError(
                "Could not find course run with courseware_id={}".format(options["run"])  # noqa: EM103
            )

        with transaction.atomic():
            successful_enrollments, edx_request_success = create_run_enrollments(
                user,
                [run],
                keep_failed_enrollments=options["keep_failed_enrollments"],
            )
            if not successful_enrollments:
                raise CommandError("Failed to create the enrollment record")  # noqa: EM101

        self.stdout.write(
            self.style.SUCCESS(
                "Enrollment created for user {} in {} (edX enrollment success: {})".format(
                    user, options["run"], edx_request_success
                )
            )
        )
