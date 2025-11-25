"""
Manage courseware objects for B2B contracts.

Allows you to
"""

import logging
from argparse import RawTextHelpFormatter

from django.core.management import BaseCommand, CommandError

from b2b.api import create_contract_run, import_and_create_contract_run
from b2b.models import ContractPage, ContractProgramItem
from courses.api import resolve_courseware_object_from_id
from courses.models import CourseRun

log = logging.getLogger(__name__)


class Command(BaseCommand):
    """Manage B2B contract courseware objects."""

    help = """Add or remove a B2B contract's courseware objects.

Courseware objects can be course runs, courses, or programs. specified by their readable ID (i.e. course-v1:MITxT+12.345s+3T2022). Contract should be specified by either their numeric ID or their slug.

Specifying courseware: You must specify one courseware item (of any type). You can specify more than one by adding "--also <courseware id>" to the end of the command. You can repeat this as many times as necessary.

To add courseware:
   b2b_courseware add [--import <departments>] [--no-create-runs] [--force] <contract> <courseware> [--also <courseware>] [--also <courseware>...]

Example: b2b_courseware add contract-100-101 program-v1:UAI+Fundamentals --also course-v1:UAI_C100+14.314x+2025_C101

Specifying "--import" will attempt to import the course run from edX if it can't be found in MITx Online. A corresponding course and course run will be created in MITx Online, and the run will be flagged as a source run. A new contract run will be created for the contract specified. The "--import" flag is ignored if a course is specified, as edX only has course runs. The "--import" flag is also ignored if a program is specified, as the command won't be able to determine what to import (again, because programs have courses, and edX doesn't have courses).

If "--import" is specified, it expects a list of departments for the new courses to be added to. This should be a list of names, separated by commas. You must specify at least one department as courses must belong to at least one department. The departments must exist; it won't create them for you.

Specifying a course run will attach it to the contract unless the contract is already attached to a contract. Specify "--force" to override any existing contract attachment.

Specifying a course will attempt to create a course run for the contract for the specified course. It will try to create a course run in edX as well unless "--no-create-runs" is specified. This flag is ignored if "--import" is specified.

Specifying a program will iterate through the program's courses and create runs for each. It will also link the program to the contract.

To remove:
    b2b_courseware remove [--remove-program-runs] contract courseware [--also courseware] [--also courseware...]

Example: b2b_courseware remove --remove-program-runs contract-100-101 program-v1:UAI+Fundamentals --also course-v1:UAI_C100+14.314x+2025_C101

Specifying a course run will unlink the run from the contract.

Specifying a course will unlink any of the course's runs that are attached to the contract from the contract.

Specifying a program will only unlink the program from the contract, unless "--remove-program-runs" is set. If it is, then all the runs that belong to both the contract and the program's courses will be removed from the contract. Note that doing this and then re-adding the program will *not* re-attach the existing runs to the contract - you will need to do that manually.
    """

    def create_run(self, contract, courseware, *, skip_edx=False):
        """Create a run for the specified contract."""
        run_tuple = create_contract_run(
            contract=contract, course=courseware, skip_edx=skip_edx
        )

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

        parser.formatter_class = RawTextHelpFormatter

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
            help="Don't create contract runs in edX for the specified course, just add it to the contract.",
            dest="create_runs",
            action="store_false",
        )
        add_subparser.add_argument(
            "--force",
            help="Force adding any specified runs to the contract (overwrite existing contract associations).",
            dest="force",
            action="store_true",
        )
        add_subparser.add_argument(
            "--import",
            help="Attempt to import course runs specified into the department(s), if they don't exist in MITx Online.",
            dest="can_import",
            type=str,
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

    def handle_add(self, contract, coursewares, **kwargs):  # noqa: PLR0915, C901
        """Handle the add subcommand."""

        create_runs = kwargs.pop("create_runs")
        force_associate = kwargs.pop("force")
        can_import = kwargs.pop("can_import")

        managed = skipped = 0

        if can_import:
            # Get the courseware IDs we got passed in that weren't matched to
            # system records. We will try to pull these in from edX.

            importable_ids = [kwargs.get("courseware", "")]
            importable_extras = kwargs.get("additional_courseware")
            if importable_extras:
                importable_ids.extend(importable_extras)

            non_importable_ids = [
                courseware.readable_id for courseware in coursewares if courseware
            ]

            for importable_id in importable_ids:
                if importable_id in non_importable_ids:
                    continue

                self.stdout.write(f"Attempting to import {importable_id} from edX...")

                imported_run, _ = import_and_create_contract_run(
                    contract=contract,
                    course_run_id=importable_id,
                    departments=can_import.split(sep=","),
                    create_cms_page=True,
                    create_depts=True,
                )

                if not imported_run:
                    self.stdout.write(
                        self.style.ERROR(f"Importing {importable_id} failed. Skipping")
                    )
                    continue

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Importing {importable_id} succeeded: {imported_run} created."
                    )
                )

        for courseware in coursewares:
            if not courseware:
                continue

            if courseware.is_program:
                # If you're specifying a program, we will always make new runs
                # since we won't be able to tell which existing ones to use.

                self.stdout.write(
                    self.style.WARNING(
                        f"'{courseware.readable_id}' is a program, so creating runs for all of its courses."
                    )
                )

                prog_add, prog_skip, prog_no_source = contract.add_program_courses(
                    courseware
                )
                if prog_no_source > 0:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Program '{courseware.readable_id}' has {prog_no_source} courses with no source runs; cannot create contract runs for these courses."
                        )
                    )
                contract.save()
                managed += prog_add
                skipped += prog_skip
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

                if self.create_run(contract, courseware, skip_edx=create_runs):
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

                ContractProgramItem.objects.filter(
                    contract=contract, program=courseware
                ).delete()
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
        courseware_id = kwargs.get("courseware", "")
        additional_courseware_ids = kwargs.get("additional_courseware")
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
