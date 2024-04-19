"""
Checks programs for a valid requirements tree. A valid tree is one that:
a) exists
b) has all the courses in the program accounted for as either an elective
   or a required course

This won't fix the issue for you - do that via Django Admin - but it will tell
you if there are any.
"""

import io
import logging

from django.core.management import BaseCommand
from django.db.models import Q

from courses.api import check_program_for_orphans
from courses.models import Program


class Command(BaseCommand):
    """
    Checks program(s) for valid requirements trees
    """

    help = "Checks program(s) for valid requirements trees"

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--program",
            action="append",
            help="Program to check.",
            nargs="*",
        )

        parser.add_argument(
            "--live", action="store_true", help="Check only live programs."
        )

    def handle(self, *args, **kwargs):  # pylint: disable=unused-argument  # noqa: ARG002
        if kwargs["program"] is not None and len(kwargs["program"]) > 0:
            numeric_ids = []
            readable_ids = []

            [
                readable_ids.append(id[0])
                if not id[0].isnumeric()
                else numeric_ids.append(id[0])
                for id in kwargs["program"]  # noqa: A001
            ]

            programs_qset = Program.objects.filter(
                Q(id__in=numeric_ids) | Q(readable_id__in=readable_ids)
            )
        else:
            programs_qset = Program.objects

        if kwargs["live"]:
            programs_qset = programs_qset.filter(live=True)

        logger = logging.getLogger("courses.api")

        log_capture = io.StringIO()
        handler = logging.StreamHandler(log_capture)

        logger.addHandler(handler)

        for program in programs_qset.all():
            orphans = check_program_for_orphans(program)

            if len(orphans) > 0:
                if "no requirements tree" in log_capture.getvalue():
                    self.stdout.write(
                        self.style.ERROR(
                            f"Program {program.readable_id} has no requirements tree!"
                        )
                    )

                self.stdout.write(
                    self.style.WARNING(
                        f"Program {program.readable_id} has {len(orphans)} orphaned course{'s' if len(orphans) > 1 else ''}:"
                    )
                )

                [
                    self.stdout.write(
                        self.style.WARNING(f"{orphan.title} - {orphan.readable_id}")
                    )
                    for orphan in orphans
                ]
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Program {program.readable_id} has a complete requirements tree"
                    )
                )

            self.stdout.write("\n")
