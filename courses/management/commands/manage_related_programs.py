"""
Manages related program records.

This takes three forms:
* Adding relationships: specify two programs to establish a relationship between
  them.
* Removing relationships: same as adding, but in reverse (with the --delete
  flag).
* Listing relationships: specify only one program to list the relationships it
  has.

"""
from django.core.management import BaseCommand, CommandError
from django.db.models import Q

from courses.models import Program
from main.utils import parse_supplied_date


class Command(BaseCommand):
    """
    Manages related program records.
    """

    help = "Manages related program records."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "first_program",
            type=str,
            help="The readable ID for the (first) program.",
        )

        parser.add_argument(
            "--second-program",
            type=str,
            help="The readable ID for the second program, if adding or removing a relationship.",
        )

        parser.add_argument(
            "--delete",
            action="store_true",
            help="Remove the relationship. This will not undo any already-granted financial assistance discounts.",
        )

    def handle(self, *args, **kwargs):
        try:
            first_program = Program.objects.filter(
                readable_id=kwargs["first_program"]
            ).get()
        except Exception as e:
            raise CommandError(f"Program {kwargs['first_program']} not found.")

        if "second_program" in kwargs and kwargs["second_program"] is not None:
            try:
                second_program = Program.objects.filter(
                    readable_id=kwargs["second_program"]
                ).get()
            except Exception as e:
                raise CommandError(f"Program {kwargs['second_program']} not found.")

            # this does create a "new" relation and then immediately deletes it if you specify --delete
            # but this'll only happen if there wasn't a relationship to begin with
            new_relation = first_program.add_related_program(second_program)

            if kwargs["delete"]:
                new_relation.delete()

            self.stdout.write(
                self.style.SUCCESS(
                    f"Relationship between {first_program.readable_id} and {second_program.readable_id} {'deleted' if kwargs['delete'] else 'created'}."
                )
            )
        else:
            self.stdout.write(
                f"Program {first_program.title} ({first_program.readable_id}) has these related programs:"
            )

            for program in first_program.related_programs:
                self.stdout.write(f"- {program.title} ({program.readable_id})")

            self.stdout.write(
                self.style.SUCCESS(
                    f"Total related programs: {len(first_program.related_programs)}"
                )
            )
