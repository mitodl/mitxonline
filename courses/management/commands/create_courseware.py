"""
Creates a courseware object. This can be a program or a course (and optionally
a course run).
"""

from django.core.management import BaseCommand

from courses.models import Course, CourseRun, Department, Program
from main.utils import parse_supplied_date


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
            start_date=(
                parse_supplied_date(kwargs["start"]) if kwargs["start"] else None
            ),
            end_date=parse_supplied_date(kwargs["end"]) if kwargs["end"] else None,
            enrollment_start=(
                parse_supplied_date(kwargs["enrollment_start"])
                if kwargs["enrollment_start"]
                else None
            ),
            enrollment_end=(
                parse_supplied_date(kwargs["enrollment_end"])
                if kwargs["enrollment_end"]
                else None
            ),
            upgrade_deadline=(
                parse_supplied_date(kwargs["upgrade"]) if kwargs["upgrade"] else None
            ),
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
            "--start",
            nargs="?",
            type=str,
            help="Start date for the course run.",
        )

        parser.add_argument(
            "--enrollment-start",
            nargs="?",
            type=str,
            help="Enrollment start date for the course run.",
        )

        parser.add_argument(
            "--end",
            nargs="?",
            type=str,
            help="End date for the course run.",
        )

        parser.add_argument(
            "--enrollment-end",
            nargs="?",
            type=str,
            help="Enrollment end date for the course run.",
        )

        parser.add_argument(
            "--upgrade",
            nargs="?",
            type=str,
            help="Upgrade deadline for the course run.",
        )

        parser.add_argument(
            "--program",
            type=str,
            nargs="?",
            help="(Course only) Add the course to the specified program (readable ID or numeric ID).",
        )

        parser.add_argument(
            "--related",
            type=str,
            nargs="?",
            action="append",
            help="(Program only) Create program relation for the specified program's readable ID. (Add as many as necessary.)",
        )

        parser.add_argument(
            "--required",
            help="(Course only) Make the course a requirement of the program.",
            action="store_true",
        )

        parser.add_argument(
            "--elective",
            help="(Course only) Make the course an elective of the program.",
            action="store_true",
        )

        parser.add_argument(
            "--force",
            "-f",
            help="Ignore some checks (swapped ID and title, requirements without live flag)",
            action="store_true",
            dest="force",
        )

        parser.add_argument(
            "-d",
            "--dept",
            "--department",
            help="Add the courseware object to the specified department(s).",
            action="append",
            dest="depts",
        )

        parser.add_argument(
            "--create-depts",
            help="If departments specified aren't found, create them.",
            action="store_true",
        )

    def handle(self, *args, **kwargs):  # pylint: disable=unused-argument
        if not (
            kwargs["force"]
            or kwargs["courseware_id"].startswith("course")
            or kwargs["courseware_id"].startswith("program")
        ):
            self.stderr.write(
                self.style.ERROR(
                    f"Object ID \"{kwargs['courseware_id']}\" would be named \"{kwargs['title']}\" - you might have your ID and title options swapped. Use --force to force creation anyway."
                )
            )
            exit(-1)

        if kwargs["depts"] and len(kwargs["depts"]) > 0:
            add_depts = Department.objects.filter(name__in=kwargs["depts"]).all()

            if kwargs["create_depts"]:
                for dept in kwargs["depts"]:
                    found = (
                        len([db_dept for db_dept in add_depts if db_dept.name == dept])
                        > 0
                    )

                    if not found:
                        new_dept = Department(name=dept)
                        new_dept.save()

                add_depts = Department.objects.filter(name__in=kwargs["depts"]).all()
        else:
            self.stderr.write(
                self.style.ERROR(
                    "Departments must be defined when creating a course or program."
                )
            )
            exit(-1)

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

            if "add_depts" in locals():
                new_program.departments.add(*add_depts)
                new_program.save()

            self.stdout.write(
                self.style.SUCCESS(
                    f"Created program {new_program.id}: {new_program.title} ({new_program.readable_id})."
                )
            )

            if kwargs["related"] is not None and len(kwargs["related"]) > 0:
                for readable_id in kwargs["related"]:
                    try:
                        related_program = Program.objects.filter(
                            readable_id=readable_id
                        ).get()
                        new_program.add_related_program(related_program)

                        self.stdout.write(
                            self.style.SUCCESS(f"Added relationship for {readable_id}.")
                        )
                    except Exception as e:
                        self.stderr.write(
                            self.style.ERROR(
                                f"Can't add relationship for {readable_id}: program not found."
                            )
                        )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Added {len(new_program.related_programs)} program relationships."
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
                title=kwargs["title"],
                readable_id=kwargs["courseware_id"],
                live=kwargs["live"],
            )

            if "add_depts" in locals():
                new_course.departments.add(*add_depts)
                new_course.save()

            self.stdout.write(
                self.style.SUCCESS(
                    f"Created course {new_course.id}: {new_course.title} ({new_course.readable_id})"
                )
            )

            if "create_run" in kwargs and kwargs["create_run"] is not None:
                run_id = f"{new_course.readable_id}+{kwargs['create_run']}"

                self.create_course_run(new_course, **kwargs)

            if kwargs["live"] or kwargs["force"]:
                if kwargs["force"]:
                    self.stderr.write(
                        self.style.ERROR(
                            f"WARNING: creating a requirement for {new_course.readable_id} anyway since you specified --force. This will probably break the Django Admin until you set the course to Live."
                        )
                    )

                new_req = None

                if program is not None and kwargs["required"]:
                    new_req = program.add_requirement(new_course)
                elif program is not None and kwargs["elective"]:
                    new_req = program.add_elective(new_course)

                if new_req is not None:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Added {new_course.readable_id} to {program.readable_id}'s {new_req.get_parent().title} requirements."
                        )
                    )
            else:
                self.stdout.write(
                    f"Live flag not specified for {new_course.readable_id}, ignoring any requirements flags"
                )
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
