"""
"Imports" a course run from the configured edX instance, and optionally creates
some infrastructure pieces to go along with it.

This will grab:
* Start/end dates
* Enrollment start/end dates
* Name
* Pacing status

from edX using the course detail API, and then will use that to create a course
run in MITx Online. Optionally, you can supply a run tag (e.g. 1T2023) and a
program (program-v1:MITx+DEDP) to have it cycle through the courses that are
associated with the program and attempt to grab courses from edX. If the course
run already exists in MITx Online, it will be skipped (the normal sync will
take care of it). If the creation is successful, this will optionally run the
create_courseware_page command for the course run.
"""

from django.core.management import BaseCommand
from django.db.models import Q

from cms.api import create_default_courseware_page
from courses.models import Course, CourseRun, Program
from openedx.api import get_edx_api_course_detail_client


class Command(BaseCommand):
    """
    Creates a courseware object.
    """

    help = "Creates a course run using details from edX."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--courserun",
            type=str,
            nargs="?",
            help="The course run to create. Do not specify with --program.",
        )

        parser.add_argument(
            "--program",
            type=str,
            nargs="?",
            help="The program to iterate through. Can be the readable ID or the database ID. Requires --run-tag. Do not specify with --courserun.",
        )

        parser.add_argument(
            "--run-tag",
            type=str,
            nargs="?",
            help="The run tag (3T2022, etc.) to use. The + will be appended to this when combining it with the course's readable ID. Requires --program. Do not specify with --courserun.",
        )

        parser.add_argument(
            "--live",
            action="store_true",
            help="Make the new course run live (defaults to not).",
        )

        parser.add_argument(
            "--create-cms-page",
            action="store_true",
            help="Create a draft CMS page for the course too",
        )

    def handle(self, *args, **kwargs):  # pylint: disable=unused-argument
        edx_course_detail = get_edx_api_course_detail_client()
        edx_courses = []

        if kwargs["courserun"] is not None:
            try:
                course = edx_course_detail.get_detail(kwargs["courserun"])

                if course is not None:
                    edx_courses.append(course)
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"Could not retrieve data for {kwargs['courserun']}: {e}"
                    )
                )
                return False
        elif kwargs["program"] is not None and kwargs["run_tag"] is not None:
            if kwargs["program"].isnumeric():
                program = Program.objects.filter(pk=kwargs["program"]).all()
            else:
                program = Program.objects.filter(readable_id=kwargs["program"]).all()

            if len(program) > 1:
                self.stdout.write(
                    self.style.ERROR(
                        f"Program ID {kwargs['program']} is ambiguous - {len(program)} results found."
                    )
                )
                return False

            program = program.first()

            for course in program.courses.all():
                if course.courseruns.filter(run_tag=kwargs["run_tag"]).count() == 0:
                    try:
                        edx_course = edx_course_detail.get_detail(
                            f"{course.readable_id}+{kwargs['run_tag']}"
                        )

                        if course is not None:
                            edx_courses.append(course)
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(
                                f"Could not retrieve data for {course.readable_id}+{kwargs['run_tag']}, skipping it: {e}"
                            )
                        )
                else:
                    self.stdout.write(
                        self.style.ERROR(
                            f"{course.readable_id}+{kwargs['run_tag']} appears to exist in MITx Online, skipping it"
                        )
                    )

        success_count = 0

        for edx_course in edx_courses:
            courserun_tag = edx_course.course_id.split("+")[-1]
            course_readable_id = edx_course.removesuffix(f"+{courserun_tag}")

            try:
                course = Course.objects.filter(readable_id=course_readable_id).get()
                new_run = CourseRun.objects.create(
                    course=course,
                    run_tag=courserun_tag,
                    courseware_id=edx_course.course_id,
                    start_date=edx_course.start,
                    end_date=edx_course.end,
                    enrollment_start=edx_course.enrollment_start,
                    enrollment_end=edx_course.enrollment_end,
                    title=edx_course.name,
                    live=kwargs["live"],
                    is_self_paced=edx_course.is_self_paced(),
                )

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created course run for {edx_course.course_id}: id {new_run.id}"
                    )
                )
                success_count += 1

                if kwargs["create_cms_page"]:
                    try:
                        create_default_courseware_page(new_run.course)
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Created CMS page for {new_run.course.readable_id}"
                            )
                        )
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(
                                f"Could not create CMS page {new_run.course.readable_id}, skipping it: {e}"
                            )
                        )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"Could not retrieve course for {edx_course.course_id}, skipping it: {e}"
                    )
                )

        self.stdout.write(self.style.SUCCESS(f"{success_count} course runs created"))
