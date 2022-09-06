"""
Management command to revoke and un revoke a certificate for a course run or program for the given user.
"""
from django.core.management.base import BaseCommand, CommandError
from users.api import fetch_user
from courses.api import (
    manage_course_run_certificate_access,
    ensure_course_run_grade,
    process_course_run_grade_certificate,
    override_user_grade,
)
from courses.models import CourseRun
from openedx.api import get_edx_grades_with_users
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    """
    Command to revoke/un-revoke a course run or program certificate for a specified user.
    """

    help = "Revoke and un revoke a certificate for a specified user against a program or course run."

    def add_arguments(self, parser):
        parser.add_argument(
            "--user",
            type=str,
            help="The id, email or username of the enrolled User",
            required=False,
        )
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            "--run", type=str, help="The 'courseware_id' value for a CourseRun"
        )
        parser.add_argument(
            "--grade",
            type=float,
            help="Override a grade. Setting grade to 0.0 blocks certificate creation. Setting a passing grade \
                (>0.0) allows certificate creation. Range: 0.0 - 1.0",
            required=False,
        )
        parser.add_argument(
            "--revoke", dest="revoke", action="store_true", required=False
        )
        parser.add_argument(
            "--unrevoke", dest="unrevoke", action="store_true", required=False
        )
        parser.add_argument(
            "--create", dest="create", action="store_true", required=False
        )

        super().add_arguments(parser)

    def handle(self, *args, **options):  # pylint: disable=too-many-locals
        """Handle command execution"""

        revoke = options.get("revoke")
        unrevoke = options.get("unrevoke")
        create = options.get("create")
        run = options.get("run")

        if not (revoke or unrevoke) and not create:
            raise CommandError(
                "The command needs a valid action e.g. --revoke, --unrevoke, --create"
            )
        try:
            user = fetch_user(options["user"]) if options["user"] else None
        except User.DoesNotExist:
            user = None

        # A run is needed for revoke/un-revoke and certificate creation
        if not run:
            raise CommandError("The command needs a valid course run")

        # Unable to obtain a run object based on the provided courseware id
        try:
            course_run = CourseRun.objects.get(courseware_id=options["run"])
        except CourseRun.DoesNotExist:
            raise CommandError(
                "Could not find run with courseware_id={}".format(options["run"])
            )

        # Handle revoke/un-revoke of a certificate
        if revoke or unrevoke:
            if not user:
                raise CommandError("Revoke/Un-revoke operation needs a valid user")

            revoke_status = manage_course_run_certificate_access(
                user=user,
                courseware_id=course_run.courseware_id,
                revoke_state=True if revoke else False,
            )

            if revoke_status:
                self.stdout.write(
                    self.style.SUCCESS(
                        "Certificate for {} has been {}".format(
                            "run: {}".format(run), "revoked" if revoke else "un-revoked"
                        )
                    )
                )
            else:
                self.stdout.write(self.style.WARNING("No changes made."))

        # Handle the creation of the certificates
        elif create:
            override_grade = options.get("grade")

            if override_grade and (override_grade < 0.0 or override_grade > 1.0):
                raise CommandError("Invalid value for grade. Allowed range: 0.0 - 1.0")

            if override_grade and not user:
                raise CommandError(
                    "Override grade needs a user (The grade override operation is not supported for multiple users)"
                )

            # If user=None, Grades for all users in this runs will be fetched
            edx_grade_user_iter = get_edx_grades_with_users(course_run, user=user)

            results = []
            is_grade_override = override_grade is not None
            for edx_grade, user in edx_grade_user_iter:
                (
                    course_run_grade,
                    created_grade,
                    updated_grade,
                ) = ensure_course_run_grade(
                    user=user,
                    course_run=course_run,
                    edx_grade=edx_grade,
                    should_update=True,
                )

                if is_grade_override:
                    # While creating certificates with grade override, we mark the user force passed if the grade is not
                    # 0.0. We don't know the grading policy set in admin for this e.g. At which percentage of marks a
                    # user can be marked passed.
                    override_user_grade(
                        user=user,
                        override_grade=override_grade,
                        courseware_id=run,
                        should_force_pass=True,
                    )

                # While overriding grade we force create the certificate
                _, created_cert, deleted_cert = process_course_run_grade_certificate(
                    course_run_grade=course_run_grade,
                    should_force_create=is_grade_override,
                )

                if created_grade:
                    grade_status = "created"
                elif updated_grade:
                    grade_status = "updated"
                else:
                    grade_status = "already exists"

                grade_summary = ["passed: {}".format(course_run_grade.passed)]
                if override_grade is not None:
                    grade_summary.append(
                        "value override: {}".format(course_run_grade.grade)
                    )

                if created_cert:
                    cert_status = "created"
                elif deleted_cert:
                    cert_status = "deleted"
                elif course_run_grade.passed:
                    cert_status = "already exists"
                else:
                    cert_status = "ignored"

                result_summary = "Grade: {} ({}), Certificate: {}".format(
                    grade_status, ", ".join(grade_summary), cert_status
                )

                results.append(
                    "Processed user {} ({}) in course run {}. Result - {}".format(
                        user.username,
                        user.email,
                        course_run.courseware_id,
                        result_summary,
                    )
                )

            for result in results:
                self.stdout.write(self.style.SUCCESS(result))
