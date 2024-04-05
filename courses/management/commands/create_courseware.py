"""
Creates a courseware object. This can be a program or a course (and optionally
a course run).
"""

from typing import List, Union

from django.core.management import BaseCommand
from django.db import models

from courses.models import Course, CourseRun, Department, Program
from main.utils import parse_supplied_date


class Command(BaseCommand):
    """
    Creates a courseware object.
    """

    help = "Creates a courseware object (a program or course, with or without a courserun)."

    def _check_if_courseware_object_readable_id_exists(
        self, courseware_object: Union[Course, Program], courseware_id: str
    ):
        """
        Queries courseware objects of the same type as the courseware_object
        parameter to see if any exist with an ID matching the courseware_id
        parameter.  If any courseware objects exist in the query, an error
        message is output and the command exits with a -1 status.

        Args:
            courseware_object (Union[Course, Program]): The type of courseware object being queried.
            courseware_id (str): The courseware ID being used in the query.
        """
        if courseware_object.objects.filter(readable_id=courseware_id).exists():
            self.stderr.write(
                self.style.ERROR(
                    f"{courseware_object.__name__} with ID {courseware_id} already exists."
                )
            )
            exit(-1)

    def _add_departments_to_courseware_object(
        self, courseware_object: Union[Course, Program], departments: models.QuerySet
    ):
        """
        Associates Departments with a Course or Program object.

        Args:
            courseware_object (Union[Course, Program]): Either a Course or Program object.
            departments (models.QuerySet): A QuerySet of Department objects.
        """
        if departments:
            for dept in departments:
                courseware_object.departments.add(dept.id)
            courseware_object.save()
        else:
            self.stderr.write(
                self.style.ERROR(
                    "There was an issue creating or adding departments to the courseware object."
                )
            )
            exit(-1)

    def _create_departments(self, departments: List[str]) -> models.QuerySet:
        """
        Creates Department objects from a list of department names (strings).

        Args:
            departments (List[str]): List of department names.

        Returns:
            models.QuerySet: Query set containing all of the departments specified
                in the list of department names.
        """
        add_depts = Department.objects.filter(name__in=departments.split()).all()
        for dept in departments.split():
            found = len([db_dept for db_dept in add_depts if db_dept.name == dept]) > 0
            if not found:
                Department.objects.create(name=dept)

        return Department.objects.filter(name__in=departments.split()).all()

    def _department_must_be_defined_error(self):
        """
        Outputs an error message indicating that departments must be
        specified when creating a course or program object
        and exits the command with a -1 status.
        """
        self.stderr.write(
            self.style.ERROR(
                "Departments must be defined when creating a course or program."
            )
        )
        exit(-1)

    def _departments_do_not_exist_error(self):
        """
        Outputs an error message indicating the specified departments
        do no currently exist and exits the command with a -1 status.
        """
        self.stderr.write(
            self.style.ERROR("The departments specified do not currently exist.")
        )
        exit(-1)

    def _successfully_created_courseware_object_message(
        self, courseware_object: Union[Course, Program]
    ):
        """
        Outputs a success message to the console in the format of
        "Created <coureware_object_type> <courseware_object_id>: <courseware_object_title> (<courseware_object_readable_id>)"

        Args:
            courseware_object (Union[Course, Program]): The courseware object that the message is related to.
        """
        self.stdout.write(
            self.style.SUCCESS(
                f"Created {courseware_object.__class__.__name__} {courseware_object.id}: {courseware_object.title} ({courseware_object.readable_id})."
            )
        )

    def _create_course_run(self, course, **kwargs):
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
            help="Specify department(s) assigned to the courseware object.",
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

        if kwargs["type"] == "program":
            if kwargs["depts"] and len(kwargs["depts"]) > 0:
                add_depts = Department.objects.filter(name__in=kwargs["depts"]).all()
            else:
                self._department_must_be_defined_error()

            if kwargs["create_depts"]:
                add_depts = self._create_departments(kwargs["depts"])
            elif not add_depts:
                self._departments_do_not_exist_error()

            self._check_if_courseware_object_readable_id_exists(
                Program, kwargs["courseware_id"]
            )

            new_program = Program.objects.create(
                readable_id=kwargs["courseware_id"],
                title=kwargs["title"],
                live=kwargs["live"],
            )

            self._add_departments_to_courseware_object(new_program, add_depts)

            self._successfully_created_courseware_object_message(new_program)

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
            self._check_if_courseware_object_readable_id_exists(
                Course, kwargs["courseware_id"]
            )

            new_course = Course.objects.create(
                title=kwargs["title"],
                readable_id=kwargs["courseware_id"],
                live=kwargs["live"],
            )

            if kwargs["depts"] and len(kwargs["depts"]) > 0:
                add_depts = Department.objects.filter(name__in=kwargs["depts"]).all()
            else:
                self._department_must_be_defined_error()

            if kwargs["create_depts"]:
                add_depts = self._create_departments(kwargs["depts"])
            if "add_depts" not in locals() or not add_depts:
                self._departments_do_not_exist_error()

            self._successfully_created_courseware_object_message(new_course)

            if "create_run" in kwargs and kwargs["create_run"] is not None:
                self._create_course_run(new_course, **kwargs)

            if kwargs["live"] or kwargs["force"]:
                if kwargs["force"]:
                    self.stderr.write(
                        self.style.ERROR(
                            f"WARNING: creating a requirement for {new_course.readable_id} anyway since you specified --force. This will probably break the Django Admin until you set the course to Live."
                        )
                    )

                new_req = None

            if "program" in kwargs and kwargs["program"] is not None:
                try:
                    program = Program.objects.filter(pk=kwargs["program"]).first()
                except:
                    program = Program.objects.filter(
                        readable_id=kwargs["program"]
                    ).first()

                self._add_departments_to_courseware_object(program, add_depts)

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

            self._create_course_run(course, **kwargs)
        else:
            self.stderr.write(self.style.ERROR(f"Not sure what {kwargs['type']} is."))
