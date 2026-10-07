"""
Check B2B contract variants for validity.
"""

from django.core.management import BaseCommand
from django.core.management.base import CommandParser

from b2b.contracts import ensure_default_variant, get_contract_variant_coverage
from b2b.management.utils import get_contract_by_id_or_slug


class Command(BaseCommand):
    """Check B2B contract variants for validity."""

    help = "Check B2B contract variants for validity."

    def add_arguments(self, parser: CommandParser) -> None:
        """Add arguments to the command."""

        parser.add_argument(
            "contract",
            type=str,
            help="The contract ID or slug to work with.",
        )
        parser.add_argument(
            "--fix-default",
            action="store_true",
            help="Add a default variant if there's not one.",
        )

    def _write_variant_set(self, entry):
        """Print one variant set and the contract's courses under it."""

        variant = entry["variant"]
        inactive = "" if variant.active else " (inactive)"

        self.stdout.write(
            f"Language = {variant.language} Industry = {variant.variant_industry} Length = {variant.variant_length}{inactive}"
        )

        if not entry["courses"] and not entry["unsupported_courses"]:
            self.stdout.write(f"\t{self.style.WARNING('NO COURSES')}")

        for listed in entry["courses"]:
            if listed["contract_run"]:
                run_status = listed["contract_run"].courseware_id
            elif listed["has_source_run"]:
                run_status = self.style.WARNING("NO RUN")
            else:
                run_status = self.style.WARNING("NO RUN, NO SOURCE RUN")

            self.stdout.write(f"\t{listed['course'].readable_id}: {run_status}")

        for listed in entry["unsupported_courses"]:
            run = listed["contract_run"]
            run_status = self.style.WARNING("NOT IN THE COURSE VARIANTS")
            if run:
                run_status = f"{run.courseware_id} {run_status}"

            self.stdout.write(f"\t{listed['course'].readable_id}: {run_status}")

    def handle(self, *_args, **kwargs):
        """Perform the check."""

        contract = kwargs.pop("contract", False)
        contract_obj = False

        contract_obj = get_contract_by_id_or_slug(contract)

        if not contract_obj:
            self.stderr.write(
                self.style.ERROR(f"Value {contract} is not a valid contract.")
            )
            return

        self.stdout.write(f"Checking for contract {contract_obj}")

        default_variant = contract_obj.default_variant_options

        if not default_variant:
            self.stderr.write(
                self.style.ERROR(
                    f"Contract {contract_obj.slug} doesn't have a default variant set."
                )
            )

            if kwargs.pop("fix_default", False):
                self.stdout.write(
                    "'fix-default' flag set, creating a default variant set for the contract."
                )
                ensure_default_variant(contract_obj)
            else:
                return

        other_options = contract_obj.variant_options.filter(default_variant=False)

        self.stdout.write(
            f"{other_options.count()} supported variants + default for contract {contract_obj.slug}"
        )

        for entry in get_contract_variant_coverage(contract_obj):
            self._write_variant_set(entry)
