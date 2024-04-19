"""
Management command to unenroll enrollment for a course run for the given User

Check the usages of this command below:

**Unenroll enrollment**

1. Unenroll enrollment for user
./manage.py unenroll_enrollment -—user=<username or email> -—run=<course_run_courseware_id>

**Keep failed enrollments**

2. Keep failed enrollments
./manage.py unenroll_enrollment -—user=<username or email> -—run=<course_run_courseware_id> -k or --keep-failed-enrollments
"""

from django.contrib.auth import get_user_model
from django.core.management.base import CommandError

from courses.api import deactivate_run_enrollment
from courses.constants import ENROLL_CHANGE_STATUS_UNENROLLED
from courses.management.utils import EnrollmentChangeCommand, enrollment_summary
from courses.models import CourseRun
from users.api import fetch_user

User = get_user_model()


class Command(EnrollmentChangeCommand):
    """Sets a user's enrollment to 'unenrolled' and deactivates it"""

    help = "Sets a user's enrollment to 'unenrolled' and deactivates it"

    def add_arguments(self, parser):
        parser.add_argument(
            "--user",
            type=str,
            help="The id, email, or username of the enrolled User",
            required=True,
        )
        parser.add_argument(
            "--run",
            type=str,
            help="The 'courseware_id' value for an enrolled CourseRun",
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
        username = options.get("user", "")
        try:
            user = fetch_user(username)
        except User.DoesNotExist:
            raise CommandError(  # noqa: B904
                f"Could not find a user with <username or email>={username}"  # noqa: EM102
            )
        courseware_id = options.get("run")
        course_run = CourseRun.objects.filter(courseware_id=courseware_id).first()
        if course_run is None:
            raise CommandError(
                f"Could not find course run with courseware_id={courseware_id}"  # noqa: EM102
            )

        keep_failed_enrollments = options.get("keep_failed_enrollments")
        enrollment, _ = self.fetch_enrollment(user, options)
        run_enrollment = deactivate_run_enrollment(
            enrollment,
            change_status=ENROLL_CHANGE_STATUS_UNENROLLED,
            keep_failed_enrollments=keep_failed_enrollments,
        )

        if run_enrollment:
            success_msg = f"Unenrolled enrollment for user: {enrollment.user.username} ({enrollment.user.email})\nEnrollment affected: {enrollment_summary(run_enrollment)}"

            self.stdout.write(self.style.SUCCESS(success_msg))
        else:
            self.stdout.write(
                self.style.ERROR(
                    "Failed to unenroll the enrollment - 'for' user: {} ({}) from course ({})\n".format(
                        user.username, user.email, options["run"]
                    )
                )
            )
