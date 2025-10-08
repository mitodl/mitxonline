"""
Manage courseware objects for B2B contracts.

This takes some of the functionality that the b2b_contract command had and moves
it here, since the b2b_contract command was getting a bit unwiedly.
"""

import logging

from django.core.management import BaseCommand, CommandError

from b2b.api import create_contract_run
from b2b.models import ContractPage
from courses.api import resolve_courseware_object_from_id

log = logging.getLogger(__name__)


class Command(BaseCommand):
    """Manage B2B contract courseware objects."""

    help = "Manage B2B contract courseware objects."

    def create_run(self, contract, courseware):
        """Create a run for the specified contract."""
        run_tuple = create_contract_run(contract=contract, course=courseware)

        if not run_tuple:
            self.stdout.write(
                self.style.ERROR(
                    f"Failed to create run for course {courseware} for contract {contract}."
                )
            )
            return False

        self.stdout.write(
            self.style.SUCCESS(
                f"Created run {run_tuple[0]} and product {run_tuple[1]} for course {courseware} for contract {contract}."
            )
        )

        return True

    def add_arugments(self, parser):
        """Add command line arguments."""

        parser.add_argument(
            "contract",
            type=str,
            help="The contract to work on (slug or ID)."
        )

        parser.add_argument(
            "courseware",
            type=str,
            help="The courseware object (readable ID) to work with. Can be a program, course, or course run.",
        )

        parser.add_argument(
            "--also",
            type=str,
            action="append",
            target="additional_courseware",
            help="Additional courseware objects (readable IDs) to work with.",
        )

        subparsers = parser.add_subparsers(
            title="Task",
            dest="subcommand",
            required=True,
            help="The task to perform - add or remove."
        )

        add_subparser = subparsers.add_parser(
            "add",
            help="Add courseware to a contract.",
        )
        remove_subparser = subparsers.add_parser(
            "remove",
            "del",
            "rm",
            help="Remove courseware from a contract.",
        )

        add_subparser.add_argument(
            "--no-create-runs",
            help="Don't create contract runs for the specified course, just add it to the contract.",
            target="create_runs",
            action="store_false",
        )
        add_subparser.add_argument(
            "--force",
            help="Force adding any specified runs to the contract (overwrite existing contract associations).",
            target="force",
            action="store_true",
        )

        remove_subparser.add_argument(
            "--program-only",
            help="Only unlink the program from the contract, don't modify course runs. (Only applies if a program is specified.)",
            action="store_true",
        )

        return super().add_arguments(parser)

    def handle_add(self, contract, coursewares, **kwargs): # noqa: ARG002
        """Handle the add subcommand."""

        create_runs = kwargs.pop("create_runs")
        force_associate = kwargs.pop("force")

        managed = skipped = 0

        for courseware in coursewares:
            courseware_id = courseware.readable_id if hasattr(courseware, "readable_id") else courseware.courseware_id

            if courseware.is_program:
                # If you're specifying a program, we will always make new runs
                # since we won't be able to tell which existing ones to use.

                self.stdout.write(
                    self.style.WARNING(
                        f"'{courseware_id}' is a program, so creating runs for all of its courses."
                    )
                )

                prog_add, prog_skip = contract.add_program_courses(courseware)
                contract.save()
                managed += prog_add
                skipped += prog_skip
            elif courseware.is_run:
                # This run already exists, so just add/remove it.
                # - If the run is owned by a different contract, skip it.
                # - If remove is True, remove the run from the contract.
                # - If remove is False, add the run to the contract.

                if not force_associate and courseware.b2b_contract and courseware.b2b_contract != contract:
                    # Already owned by another contract, so skip
                    self.stdout.write(
                        self.style.WARNING(
                            f"Run '{courseware_id}' is already owned by {courseware.b2b_contract}."
                        )
                    )
                    skipped += 1
                    continue
                elif courseware.b2b_contract == contract:
                    # Already owned by this contract, so skip
                    self.stdout.write(
                        self.style.WARNING(
                            f"Run '{courseware_id}' is already owned by this contract."
                        )
                    )
                    skipped += 1
                else:
                    # Add the run to the contract
                    courseware.b2b_contract = contract
                    courseware.save()
                    managed += 1
            elif create_runs:
                # This is a course, so create a run (unless we've been told not to).

                if self.create_run(contract, courseware):
                    managed += 1
                else:
                    skipped += 1
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipped run creation for for course {courseware} for contract {contract}."
                    )
                )
                skipped += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Managed {managed} courseware items and skipped {skipped} courseware items for {len(coursewares)} specified courseware IDs."
            )
        )


    def handle(self, *args, **kwargs):
        """Dispatch the requested task."""

        contract_id = kwargs.pop("contract")
        courseware_id = kwargs.pop("courseware")
        additional_courseware_ids = kwargs.pop("additional_courseware")
        subcommand = kwargs.pop("subcommand")

        contract = ContractPage.objects.filter(slug=contract_id).first()
        if not contract:
            contract = ContractPage.objects.filter(id=contract_id).first()

        if not contract:
            msg = f"Contract with ID/slug '{contract_id}' does not exist."
            raise CommandError(msg)

        coursewares = [ resolve_courseware_object_from_id(courseware_id) for courseware_id in [ courseware_id, *additional_courseware_ids ] ]

        if subcommand == "add":
            return self.handle_add(contract, coursewares, **kwargs)

        self.stderr.write(self.style.ERROR(f"Unknown command {subcommand}"))
        return False
