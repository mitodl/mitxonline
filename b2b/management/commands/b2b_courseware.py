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
from courses.models import CourseRun

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

    def add_arguments(self, parser):
        """Add command line arguments."""

        subparsers = parser.add_subparsers(
            title="Task",
            dest="subcommand",
            required=True,
            help="The task to perform - add or remove.",
        )
        parser.add_argument(
            "contract", type=str, help="The contract to work on (slug or ID)."
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
            dest="additional_courseware",
            help="Additional courseware objects (readable IDs) to work with.",
        )

        add_subparser = subparsers.add_parser(
            "add",
            help="Add courseware to a contract.",
        )
        add_subparser.add_argument(
            "--no-create-runs",
            help="Don't create contract runs for the specified course, just add it to the contract.",
            dest="create_runs",
            action="store_false",
        )
        add_subparser.add_argument(
            "--force",
            help="Force adding any specified runs to the contract (overwrite existing contract associations).",
            dest="force",
            action="store_true",
        )

        remove_subparser = subparsers.add_parser(
            "remove",
            help="Remove courseware from a contract.",
        )

        remove_subparser.add_argument(
            "--remove-program-runs",
            help="For programs, unlink the program's contract runs as well as the program.",
            action="store_true",
        )

        return super().add_arguments(parser)

    def handle_add(self, contract, coursewares, **kwargs):
        """Handle the add subcommand."""

        create_runs = kwargs.pop("create_runs")
        force_associate = kwargs.pop("force")

        managed = skipped = 0

        for courseware in coursewares:
            if courseware.is_program:
                # If you're specifying a program, we will always make new runs
                # since we won't be able to tell which existing ones to use.

                self.stdout.write(
                    self.style.WARNING(
                        f"'{courseware.readable_id}' is a program, so creating runs for all of its courses."
                    )
                )

                prog_add, prog_skip = contract.add_program_courses(courseware)
                contract.save()
                managed += prog_add
                skipped += prog_skip
                contract.programs.add(courseware)
                self.stdout.write(
                    self.style.SUCCESS(f"Added {courseware.readable_id} to {contract}.")
                )
            elif courseware.is_run:
                # This run already exists, so:
                # - If it's in a contract already and we're not forcing it, skip it.
                # - If it's in a contract already and we *are* forcing it, set it to be in this contract.
                # - If it's not in a contract, add it to this contract.

                if (
                    not force_associate
                    and courseware.b2b_contract
                    and courseware.b2b_contract != contract
                ):
                    # Already owned by another contract, so skip
                    self.stdout.write(
                        self.style.WARNING(
                            f"Run '{courseware.courseware_id}' is already owned by {courseware.b2b_contract}."
                        )
                    )
                    skipped += 1
                    continue
                elif courseware.b2b_contract == contract:
                    # Already owned by this contract, so skip
                    self.stdout.write(
                        self.style.WARNING(
                            f"Run '{courseware.courseware_id}' is already owned by this contract."
                        )
                    )
                    skipped += 1
                    continue

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
                        f"Skipped run creation for for course {courseware.readable_id} for contract {contract}."
                    )
                )
                skipped += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Managed {managed} courseware items and skipped {skipped} courseware items for {len(coursewares)} specified courseware IDs."
            )
        )

        return True

    def handle_remove(self, contract, coursewares, **kwargs):
        """Handle removing courseware from a contract."""

        remove_runs = kwargs.pop("remove_program_runs")

        for courseware in coursewares:
            if courseware.is_program:
                # If we have a program, unlink the program from the contract.
                # Then, if we're told to, unlink any contract runs that are
                # part of the program too.

                if remove_runs:
                    program_courses = courseware.courses
                    program_runs = CourseRun.objects.filter(
                        b2b_contract=contract,
                        course__in=[course for (course, _) in program_courses],
                    ).all()

                    coursewares.extend(program_runs)

                    self.stdout.write(
                        self.style.NOTICE(
                            f"{courseware.readable_id} is a program and --remove-program-runs set, so adding {len(program_runs)} course runs"
                        )
                    )

                contract.programs.remove(courseware)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Removed program {courseware.readable_id} from contract {contract}."
                    )
                )
            elif not courseware.is_run:
                # If we have a course, find and add the contract runs for the
                # course to the list. We don't link courses to contracts, so
                # there's nothing else to do here.

                course_contract_runs = courseware.courseruns.filter(
                    b2b_contract=contract
                ).all()

                coursewares.extend(course_contract_runs)

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Added {len(course_contract_runs)} course runs from course {courseware.readable_id} to remove from contract {contract}."
                    )
                )
            else:
                # We're actually at a course run now.

                courseware.b2b_contract = None
                courseware.save()

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Unlinked {courseware.courseware_id} from {contract}."
                    )
                )

        return True

    def handle(self, *args, **kwargs):  # noqa: ARG002
        """Dispatch the requested task."""

        contract_id = kwargs.pop("contract")
        courseware_id = kwargs.pop("courseware")
        additional_courseware_ids = kwargs.pop("additional_courseware")
        subcommand = kwargs.pop("subcommand")

        if contract_id.isdecimal():
            contract = ContractPage.objects.filter(id=contract_id).first()
        else:
            contract = ContractPage.objects.filter(slug=contract_id).first()

        if not contract:
            msg = f"Contract with ID/slug '{contract_id}' does not exist."
            raise CommandError(msg)

        courseware_ids = [courseware_id]
        if additional_courseware_ids:
            courseware_ids.extend(additional_courseware_ids)

        coursewares = [
            resolve_courseware_object_from_id(courseware_id)
            for courseware_id in courseware_ids
        ]

        if subcommand == "add":
            self.handle_add(contract, coursewares, **kwargs)
        elif subcommand == "remove":
            self.handle_remove(contract, coursewares, **kwargs)
        else:
            self.stderr.write(self.style.ERROR(f"Unknown command {subcommand}"))
