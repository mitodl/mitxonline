"""Management command to change enrollment status"""

from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.management.base import CommandError

from courses.api import defer_enrollment
from courses.management.utils import EnrollmentChangeCommand, enrollment_summary
from courses.models import CourseRun, CourseRunEnrollment
from users.api import fetch_user

User = get_user_model()


class Command(EnrollmentChangeCommand):
    """Sets a user's enrollment to 'deferred' and creates an enrollment for a different course run"""

    help = "Sets a user's enrollment to 'deferred' and creates an enrollment for a different course run"

    def add_arguments(self, parser):
        parser.add_argument(
            "--user",
            type=str,
            help="The id, email, or username of the enrolled User",
            required=True,
        )
        parser.add_argument(
            "--from-run",
            type=str,
            help="The 'courseware_id' value for an enrolled CourseRun",
            required=True,
        )
        parser.add_argument(
            "--to-run",
            type=str,
            help="The 'courseware_id' value for the CourseRun that you are deferring to",
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
        from_courseware_id = options["from_run"]
        to_courseware_id = options["to_run"]

        try:
            from_enrollment, to_enrollment = defer_enrollment(
                user,
                from_courseware_id,
                to_courseware_id,
                keep_failed_enrollments=options["keep_failed_enrollments"],
                force=options["force"],
            )
        except ObjectDoesNotExist as exc:
            if isinstance(exc, CourseRunEnrollment.DoesNotExist):
                message = f"'from' course run enrollment does not exist ({from_courseware_id})"
            elif isinstance(exc, CourseRun.DoesNotExist):
                message = f"'to' course does not exist ({to_courseware_id})"
            else:
                message = str(exc)
            raise CommandError(message)  # noqa: B904
        except ValidationError as exc:
            raise CommandError(f"Invalid enrollment deferral - {exc}")  # noqa: B904, EM102
        except Exception as exc:  # noqa: BLE001
            raise CommandError(f"{exc}")  # noqa: B904, EM102
        else:
            if not to_enrollment:
                raise CommandError(
                    f"Failed to create/update the target enrollment ({to_courseware_id})"  # noqa: EM102
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Deferred enrollment for user: {user}\n"
                f"Enrollment deactivated: {enrollment_summary(from_enrollment)}\n"
                f"Enrollment created/updated: {enrollment_summary(to_enrollment)}"
            )
        )
