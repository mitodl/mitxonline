"""
Manage courseware objects for B2B contracts.

Allows you to
"""

import logging
from argparse import RawTextHelpFormatter

from django.core.management import BaseCommand, CommandError
from opaque_keys import InvalidKeyError

from b2b.api import import_and_create_contract_run
from b2b.contracts import add_courseware_to_contract, remove_courseware_from_contract
from b2b.models import ContractPage
from b2b.tasks import queue_enrollment_code_check
from courses.api import resolve_courseware_object_from_id
from courses.constants import UAI_COURSEWARE_ID_PREFIX

log = logging.getLogger(__name__)


class Command(BaseCommand):
    """Manage B2B contract courseware objects."""

    help = """Add or remove a B2B contract's courseware objects.

Courseware objects can be course runs, courses, or programs. specified by their readable ID (i.e. course-v1:MITxT+12.345s+3T2022). Contract should be specified by either their numeric ID or their slug.

Specifying courseware: You must specify one courseware item (of any type). You can specify more than one by adding "--also <courseware id>" to the end of the command. You can repeat this as many times as necessary.

To add courseware:
   b2b_courseware add [--import <departments>] [--no-create-runs] [--force] [--prefix <prefix>] [--make-codes] <contract> <courseware> [--also <courseware>] [--also <courseware>...]

Example: b2b_courseware add contract-100-101 program-v1:UAI+Fundamentals --also course-v1:UAI_C100+14.314x+2025_C101

Specifying "--import" will attempt to import the course run from edX if it can't be found in MITx Online. A corresponding course and course run will be created in MITx Online, and the run will be flagged as a source run. A new contract run will be created for the contract specified. The "--import" flag is ignored if a course is specified, as edX only has course runs. The "--import" flag is also ignored if a program is specified, as the command won't be able to determine what to import (again, because programs have courses, and edX doesn't have courses).

If "--import" is specified, it expects a list of departments for the new courses to be added to. This should be a list of names, separated by commas. You must specify at least one department as courses must belong to at least one department. The departments must exist; it won't create them for you.

Specifying a course run will attach it to the contract unless the contract is already attached to a contract. Specify "--force" to override any existing contract attachment.

Specifying a course will attempt to create a course run for the contract for the specified course. It will try to create a course run in edX as well unless "--no-create-runs" is specified. This flag is ignored if "--import" is specified.

Specifying a course will create course runs for variant options if:
- The course has supported variants, and there are source runs for those variants
- The contract has supported variants
- The course and contract variants agree to any extent

E.g.: adding a course with 5 variants (and source runs) to a contract that has 3 variants will result in contract runs for variants that match up between the contract and course. (This will usually include the standard default set but that's not a guarantee.)

You can also filter on variant options by using the --variant flag. Filtering in this manner will not include the default - make sure to include it if you want it.

Specifying a program will iterate through the program's courses and create runs for each. It will also link the program to the contract. Variant runs will be created for each course in the program, according to the rules above.

To remove:
    b2b_courseware remove [--remove-program-runs] contract courseware [--also courseware] [--also courseware...]

Example: b2b_courseware remove --remove-program-runs contract-100-101 program-v1:UAI+Fundamentals --also course-v1:UAI_C100+14.314x+2025_C101

Specifying a course run will unlink the run from the contract.

Specifying a course will unlink any of the course's runs that are attached to the contract from the contract.

Specifying a program will only unlink the program from the contract, unless "--remove-program-runs" is set. If it is, then all the runs that belong to both the contract and the program's courses will be removed from the contract. Note that doing this and then re-adding the program will *not* re-attach the existing runs to the contract - you will need to do that manually.
    """

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
            dest="no_create_runs",
            action="store_true",
        )
        add_subparser.add_argument(
            "--allow-reruns",
            help="Allow courses to be re-run.",
            dest="allow_reruns",
            action="store_true",
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
        add_subparser.add_argument(
            "--prefix",
            help=f"Organization prefix for the resulting course run. (Defaults to the org setting, or {UAI_COURSEWARE_ID_PREFIX}.)",
            type=str,
        )
        add_subparser.add_argument(
            "--make-codes",
            action="store_true",
            help="Create enrollment codes after adding course(s) to the contract. (Skips this by default; run b2b_codes validate afterward if the contract requires codes.)",
        )
        add_subparser.add_argument(
            "--no-lang",
            action="store_true",
            help="Ignore languages - only create runs for the primary language (or the blank language)",
        )
        add_subparser.add_argument(
            "--lang",
            type=str,
            help="Include the default and the specified language code only.",
        )
        add_subparser.add_argument(
            "--variant",
            type=str,
            action="append",
            default=[],
            help="Limit to variant(s) specified. Specify as comma-separated values in format 'lang,industry,length'. Repeat as necessary.",
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

    def handle_add(self, contract, coursewares, **kwargs):  # noqa: C901, PLR0915
        """Handle the add subcommand."""

        skip_edx = kwargs.pop("no_create_runs", False)
        force_associate = kwargs.pop("force")
        can_import = kwargs.pop("can_import")
        org_prefix = kwargs.pop("prefix")
        make_codes = kwargs.pop("make_codes", False)
        no_reruns = not kwargs.pop("allow_reruns", True)
        ignore_langs = kwargs.pop("no_lang", False)
        only_lang = kwargs.pop("lang", None)
        variants = kwargs.pop("variant", [])

        managed = 0

        # Parse out the variants specified.
        filter_variants = (
            list(contract.variant_options.all()) if len(variants) == 0 else []
        )

        for variant in variants:
            opts = variant.split(",")
            filter_val = contract.variant_options
            if len(opts) >= 1:
                filter_val = filter_val.filter(language=opts[0])
            if len(opts) >= 2:  # noqa: PLR2004
                filter_val = filter_val.filter(variant_industry=opts[1])
            if len(opts) == 3:  # noqa: PLR2004
                filter_val = filter_val.filter(variant_length=opts[2])
            if len(opts) > 3:  # noqa: PLR2004
                self.stderr.write(
                    self.style.ERROR(f"Bad variant options specified: {opts}")
                )
                return -1

            filter_val = filter_val.first()
            if filter_val:
                filter_variants.append(filter_val)

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

                imported_runs = import_and_create_contract_run(
                    contract=contract,
                    course_run_id=importable_id,
                    departments=can_import.split(sep=","),
                    create_cms_page=True,
                    create_depts=True,
                    org_prefix=org_prefix,
                )

                if not imported_runs:
                    self.stdout.write(
                        self.style.ERROR(f"Importing {importable_id} failed. Skipping")
                    )
                    continue
                imported_run = imported_runs[0][0]

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Importing {importable_id} succeeded: {imported_run} created."
                    )
                )

        for courseware in coursewares:
            if not courseware:
                continue

            if courseware.is_program:
                self.stdout.write(
                    self.style.WARNING(
                        f"'{courseware.readable_id}' is a program, so creating runs for all of its courses."
                    )
                )

            try:
                added = add_courseware_to_contract(
                    contract,
                    courseware,
                    skip_edx=skip_edx,
                    no_reruns=no_reruns,
                    force=force_associate,
                    org_prefix=org_prefix,
                    ignore_langs=ignore_langs,
                    only_lang=only_lang,
                    filter_variants=filter_variants,
                )
            except InvalidKeyError:
                self.stderr.write(
                    self.style.ERROR(
                        f"Invalid key error for course {courseware}. Is the course's readable ID configured correctly?"
                    )
                )
                continue

            if added.skipped_reason:
                self.stdout.write(self.style.WARNING(added.skipped_reason))
                continue

            if added.courses_without_source_run:
                self.stdout.write(
                    self.style.WARNING(
                        f"Program '{courseware.readable_id}' has {added.courses_without_source_run} courses with no source runs; cannot create contract runs for these courses."
                    )
                )

            if not added.runs_added and not courseware.is_program:
                self.stdout.write(
                    self.style.ERROR(
                        f"Failed to create run for course {courseware} for contract {contract}."
                    )
                )
                continue

            managed += added.runs_added
            self.stdout.write(
                self.style.SUCCESS(
                    f"Added {courseware.readable_id} to {contract} ({added.runs_added} runs)."
                )
            )

        if make_codes:
            self.stdout.write(f"Queueing enrollment code check for {contract}")
            queue_enrollment_code_check.delay(contract.id)

        self.stdout.write(
            self.style.SUCCESS(
                f"Managed {managed} courseware items for {len(coursewares)} specified courseware IDs."
            )
        )

        return True

    def handle_remove(self, contract, coursewares, **kwargs):
        """Handle removing courseware from a contract."""

        remove_runs = kwargs.pop("remove_program_runs")

        for courseware in coursewares:
            removed = remove_courseware_from_contract(
                contract, courseware, remove_program_runs=remove_runs
            )

            if courseware.is_program:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Removed program {courseware.readable_id} from contract {contract}, with {len(removed)} of its runs."
                    )
                )

            for run, unlinked in removed:
                if unlinked:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Deactivated and unlinked {run.courseware_id} from {contract} (no enrollments)."
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Deactivated {run.courseware_id} but kept it linked to {contract} (has enrollments)."
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
