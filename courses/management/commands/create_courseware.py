"""
Creates a courseware object. This can be a program or a course (and optionally
a course run).
"""
from django.core.management import BaseCommand

from courses.models import Program, Course, CourseRun


class Command(BaseCommand):
    """
    Creates a courseware object.
    """

    help = "Creates a courseware object (a program or course, with or without a courserun)."

    def create_course_run(self, course, **kwargs):
        run_id = f"{course.readable_id}+{kwargs['create_run']}"

        if CourseRun.objects.filter(
            run_tag=kwargs["create_run"], course=course
        ).exists():
            self.stderr.write(
                self.style.ERROR(
                    f"Course run for {course} with ID {kwargs['create_run']} already exists."
                )
            )
            exit(-1)

        course_run = CourseRun.objects.create(
            course=course,
            title=kwargs["title"],
            run_tag=kwargs["create_run"],
            courseware_id=run_id,
            courseware_url_path=kwargs["run_url"],
            live=kwargs["live"],
            is_self_paced=kwargs["self_paced"],
        )

        self.stdout.write(
            self.style.SUCCESS(f"Created course run {course_run.id}: {course_run}")
        )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "type",
            choices=["program", "course", "courserun"],
            help="The courseware object to create (program, course, or courserun).",
        )

        parser.add_argument(
            "courseware_id",
            type=str,
            help="The readable ID for the courseware object. (For course runs, do not include the run tag.)",
        )

        parser.add_argument("title", type=str, help="The title of the object.")

        parser.add_argument(
            "--live",
            action="store_true",
            help="Make the object live (defaults to not).",
        )

        parser.add_argument(
            "--self-paced",
            action="store_true",
            help="(Course run only) Make the course run self-paced.",
        )

        parser.add_argument(
            "--create-run",
            "--run-tag",
            nargs="?",
            type=str,
            help="(Course and course run only) Create a run with the specified tag.",
            metavar="create_run",
        )

        parser.add_argument(
            "--run-url",
            type=str,
            nargs="?",
            help="(Course and course run only) Create a run with the specified URL path.",
        )

        parser.add_argument(
            "--program",
            type=str,
            nargs="?",
            help="(Course only) Add the course to the specified program (readable ID or numeric ID).",
        )

        parser.add_argument(
            "--program-position",
            type=str,
            nargs="?",
            help="(Course only) The position the course should be in the program.",
        )

    def handle(self, *args, **kwargs):  # pylint: disable=unused-argument
        if kwargs["type"] == "program":
            if Program.objects.filter(readable_id=kwargs["courseware_id"]).exists():
                self.stderr.write(
                    self.style.ERROR(
                        f"Program with ID {kwargs['courseware_id']} already exists."
                    )
                )
                exit(-1)

            new_program = Program.objects.create(
                readable_id=kwargs["courseware_id"],
                title=kwargs["title"],
                live=kwargs["live"],
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Created program {new_program.id}: {new_program.title} ({new_program.readable_id})."
                )
            )
        elif kwargs["type"] == "course":
            if Course.objects.filter(readable_id=kwargs["courseware_id"]).exists():
                self.stderr.write(
                    self.style.ERROR(
                        f"Course with ID {kwargs['courseware_id']} already exists."
                    )
                )
                exit(-1)

            program = None

            if "program" in kwargs and kwargs["program"] is not None:
                try:
                    program = Program.objects.filter(pk=kwargs["program"]).first()
                except:
                    program = Program.objects.filter(
                        readable_id=kwargs["program"]
                    ).first()

            new_course = Course.objects.create(
                program=program,
                title=kwargs["title"],
                readable_id=kwargs["courseware_id"],
                live=kwargs["live"],
                position_in_program=kwargs["program_position"],
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Created course {new_course.id}: {new_course.title} ({new_course.readable_id}) in program {new_course.program}"
                )
            )

            if "create_run" in kwargs and kwargs["create_run"] is not None:
                run_id = f"{new_course.readable_id}+{kwargs['create_run']}"

                self.create_course_run(new_course, **kwargs)
        elif kwargs["type"] == "courserun":
            if not Course.objects.filter(readable_id=kwargs["courseware_id"]).exists():
                self.stderr.write(
                    self.style.ERROR(
                        f"Course with ID {kwargs['courseware_id']} doesn't exist."
                    )
                )
                exit(-1)

            if "create_run" not in kwargs or kwargs["create_run"] is None:
                self.stderr.write(
                    self.style.ERROR(
                        "You must specify the run tag with either --run-tag or --create-run when creating a course run."
                    )
                )
                exit(-1)

            course = Course.objects.filter(readable_id=kwargs["courseware_id"]).get()

            self.create_course_run(course, **kwargs)
        else:
            self.stderr.write(self.style.ERROR(f"Not sure what {kwargs['type']} is."))
