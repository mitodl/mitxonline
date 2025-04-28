"""
Management command to retry edX enrollment for a user's course run enrollments
"""

from django.contrib.auth import get_user_model
from django.core.management import BaseCommand

from courses.models import CourseRunEnrollment
from openedx.api import enroll_in_edx_course_runs
from users.api import fetch_users

User = get_user_model()


class Command(BaseCommand):
    """
    Management command to retry edX enrollment for a user's course run enrollments
    """

    help = "Fetches users' course run enrollments and reattempts enrollment via the edX API."

    def add_arguments(self, parser):
        """
        Definition of arguments this command accepts
        """
        parser.add_argument(
            "-f",
            "--force",
            action="store_true",
            help="Retry edX enrollment even if the target users enrollments indicate edx_enrolled=True",
        )
        parser.add_argument(
            "--run", type=str, help="The 'courseware_id' value for a target CourseRun"
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
        enrollment_filter = {}
        if not options["force"]:
            enrollment_filter["edx_enrolled"] = False
        if options["run"]:
            enrollment_filter["run__courseware_id"] = options["run"]
        if options["uservalues"]:
            enrollment_filter["user__in"] = fetch_users(options["uservalues"])
        course_run_enrollments = CourseRunEnrollment.objects.filter(**enrollment_filter)

        if course_run_enrollments.count() == 0:
            self.stderr.write(
                self.style.ERROR(
                    f"No course run enrollments found that match the given filters ({enrollment_filter}).\nExiting..."
                )
            )
            return

        for enrollment in course_run_enrollments:
            user = enrollment.user
            course_run = enrollment.run
            try:
                enroll_in_edx_course_runs(
                    user, [course_run], mode=enrollment.enrollment_mode
                )
            except Exception as exc:  # pylint: disable=broad-except  # noqa: BLE001
                self.stderr.write(self.style.ERROR(f"{exc!s}"))
            else:
                enrollment.edx_enrolled = True
                enrollment.edx_emails_subscription = True
                enrollment.save_and_log(None)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully enrolled user {user.edx_username} ({user.email}) in course run '{course_run.courseware_id}'"
                    )
                )

        self.stdout.write(self.style.SUCCESS("Done"))
