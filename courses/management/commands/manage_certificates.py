"""
Management command to revoke, un revoke or create a certificate for a course run for the given User
or Users when no user is provided.

Check the usages of this command below:

**Certificate Creation**

1. Sync grades with edX and generate certificates. (For all users)
./manage.py manage_certificates -—create -—run=<course_run_courseware_id>

2. Sync grades with edX and generate certificate. (For single user)
./manage.py manage_certificates —-create -—run=<course_run_courseware_id> -—user=<username or email>

3. Override grade for a user and generate certificate. (For single user, will force create the certificate for the user)
./manage.py manage_certificates -—create  -—run=<course_run_courseware_id> —-user=<username or email> -—grade=<a float value between 0.0-1.0>

**Revoke/Un-revoke Certificates**

4. Revoke a certificate (Only available for single user)
./mange.py manage_certificates -—revoke -—user=<username or email> -—run=<course_run_courseware_id>

5. Un-Revoke a certificate (Only available for single user)
./mange.py manage_certificates -—unrevoke —-run=<course_run_courseware_id> -—user=<username or email>

"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from courses.api import (
    ensure_course_run_grade,
    manage_course_run_certificate_access,
    override_user_grade,
    process_course_run_grade_certificate,
)
from courses.models import CourseRun
from courses.utils import is_grade_valid
from openedx.api import get_edx_grades_with_users
from users.api import fetch_user

User = get_user_model()


class Command(BaseCommand):
    """
    Invoke with:

        python manage.py manage_certificates
    """

    help = (
        "Revoke, un revoke or create a certificate for a course run for the given User "
        "or Users when no user is provided"
    )

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
        override_grade = options.get("grade")

        if not (revoke or unrevoke) and not create:
            raise CommandError(
                "The command needs a valid action e.g. --revoke, --unrevoke, --create."
            )
        try:
            user = fetch_user(options["user"]) if options["user"] else None
        except User.DoesNotExist:
            user = None

        # A run is needed for revoke/un-revoke and certificate creation
        if not run:
            raise CommandError("The command needs a valid course run.")

        # Unable to obtain a run object based on the provided courseware id
        try:
            course_run = CourseRun.objects.get(courseware_id=run)
        except CourseRun.DoesNotExist:
            raise CommandError("Could not find run with courseware_id={}.".format(run))

        # Handle revoke/un-revoke of a certificate
        if revoke or unrevoke:
            if not user:
                raise CommandError("Revoke/Un-revoke operation needs a valid user.")

            revoke_status = manage_course_run_certificate_access(
                user=user,
                courseware_id=course_run.courseware_id,
                revoke_state=True if revoke else False,
            )

            if revoke_status:
                self.stdout.write(
                    self.style.SUCCESS(
                        "Certificate for {} has been {}".format(
                            "run: {}".format(run),
                            "revoked." if revoke else "un-revoked.",
                        )
                    )
                )
            else:
                self.stdout.write(self.style.WARNING("No changes made."))

        # Handle the creation of the certificates.
        # Also check if the certificate creation was requested with grade override. (Generally useful when we want to
        # create a certificate for a user while overriding the grade value)
        elif create:

            if override_grade and not is_grade_valid(override_grade):
                raise CommandError("Invalid value for grade. Allowed range: 0.0 - 1.0.")

            if override_grade and not user:
                raise CommandError(
                    "Override grade needs a user (The grade override operation is not supported for multiple users)."
                )

            # If user=None, Grades for all users in the run will be fetched
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
                (
                    certificate,
                    created_cert,
                    deleted_cert,
                ) = process_course_run_grade_certificate(
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
                elif course_run_grade.passed and certificate:
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
