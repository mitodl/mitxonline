"""
Management command to create locals enrollments for specific runs from edX in bulk. It doesn't handle updates to local
enrollment if exists.
To sync enrollments for specific user and from both direction, use sync_enrollments command instead.

./manage.py create_local_enrollments -—runs=<list of courseware IDs separated by space>

"""

from django.core.management.base import BaseCommand

from courses.models import CourseRun, CourseRunEnrollment, User
from openedx.api import get_edx_api_service_client


class Command(BaseCommand):
    """creates local enrollments for specific runs from edX"""

    help = "Creates local enrollments for specific runs from edX"

    def add_arguments(self, parser):
        parser.add_argument(
            "--runs",
            nargs="*",
            type=str,
            help="list of courseware_ids e.g. --runs course-v1:edX+E2E-101+course course-v1:edX+DemoX+Demo_Course",
            required=True,
        )

    def handle(self, *args, **options):  # noqa: ARG002
        """Handle command execution"""

        courseware_ids = options["runs"]

        edx_client = get_edx_api_service_client()
        
        runs_by_courseware_id = CourseRun.objects.in_bulk(
            courseware_ids, field_name="courseware_id"
        )

        created_count = {}
        for courseware_id in courseware_ids:
            run = runs_by_courseware_id.get(courseware_id)
            if run is None:
                self.stderr.write(
                    self.style.ERROR(
                        f"Could not find course run with courseware_id={courseware_id}"
                    )
                )
                continue

            edx_enrollments = edx_client.enrollments.get_enrollments(
                course_id=courseware_id
            )

            created_count[courseware_id] = 0
            for edx_enrollment in edx_enrollments:
                try:
                    user = User.objects.filter(username=edx_enrollment.user).first()
                    if user:
                        (
                            _,
                            created,
                        ) = CourseRunEnrollment.all_objects.get_or_create(
                            user=user,
                            run=run,
                            defaults=dict(  # noqa: C408
                                active=edx_enrollment.is_active,
                                change_status=None,
                                edx_emails_subscription=False,
                                edx_enrolled=True,
                                enrollment_mode=edx_enrollment.mode,
                            ),
                        )
                        if created:
                            created_count[courseware_id] += 1

                except:  # noqa: PERF203, E722
                    self.stderr.write(
                        self.style.ERROR(
                            f"Could not get or create course enrollment for user {edx_enrollment.user} course ID {courseware_id}"
                        )
                    )

        for courseware_id, count in created_count.items():
            self.stdout.write(
                self.style.SUCCESS(
                    f"\t{count} Enrollments created for {courseware_id} "
                )
            )
