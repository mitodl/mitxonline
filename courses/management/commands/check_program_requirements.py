"""
Reports programs whose saved requirement tree is missing or breaks a rule that
courses.requirement_tree.validate_requirement_tree enforces on save, which is
how a tree saved before a rule existed is found.

This won't fix the issue for you - do that via Django Admin - but it will tell
you if there are any.
"""

from django.core.management import BaseCommand
from django.db.models import Q

from courses.models import Program, ProgramRequirement
from courses.requirement_tree import validate_requirement_tree


class Command(BaseCommand):
    """
    Checks program(s) for valid requirements trees
    """

    help = "Checks program(s) for valid requirements trees"

    def add_arguments(self, parser) -> None:
        """Add --program (repeatable) and --live"""
        parser.add_argument(
            "--program",
            action="append",
            help="Program to check, by id or readable_id.",
            nargs="*",
        )

        parser.add_argument(
            "--live", action="store_true", help="Check only live programs."
        )

    def handle(self, *args, **kwargs):  # noqa: ARG002
        """Report every selected program whose tree is missing or breaks a rule"""
        if kwargs["program"]:
            program_ids = [pid for group in kwargs["program"] for pid in group]
            programs_qset = Program.objects.filter(
                Q(id__in=[pid for pid in program_ids if pid.isnumeric()])
                | Q(readable_id__in=[pid for pid in program_ids if not pid.isnumeric()])
            )
        else:
            programs_qset = Program.objects.all()

        if kwargs["live"]:
            programs_qset = programs_qset.filter(live=True)

        invalid = 0
        for program in programs_qset.order_by("readable_id"):
            root = program.get_requirements_root()
            if root is None:
                invalid += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"Program {program.readable_id} has no requirements tree"
                    )
                )
                continue
            tree = ProgramRequirement.dump_bulk(parent=root, keep_ids=True)[0].get(
                "children", []
            )
            errors = validate_requirement_tree(tree, display_mode=program.display_mode)
            if errors:
                invalid += 1
            for error in errors:
                self.stdout.write(
                    self.style.WARNING(f"Program {program.readable_id}: {error}")
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Checked {programs_qset.count()} program(s); {invalid} with problems"
            )
        )
