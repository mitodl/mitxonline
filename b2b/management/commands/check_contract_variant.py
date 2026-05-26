"""
Check B2B contract variants for validity.
"""

from django.core.management import BaseCommand
from django.core.management.base import CommandParser

from b2b.models import ContractPage
from variants.models import SupportedVariant


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

    def handle(self, *_args, **kwargs):
        """Perform the check."""

        contract = kwargs.pop("contract", False)
        contract_obj = False

        if contract.isdecimal():
            contract_obj = ContractPage.objects.filter(id=contract).first()
        else:
            contract_obj = ContractPage.objects.filter(slug=contract).first()

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
                default_variant = SupportedVariant.objects.create(
                    variant_object=contract_obj,
                    language="en",
                    b2b_only=False,
                    default_variant=True,
                )
            else:
                return

        other_options = contract_obj.variant_options.filter(default_variant=False)

        self.stdout.write(
            f"{len(other_options)} supported variants + default for contract {contract_obj.slug}"
        )

        runs_qs = contract_obj.get_variant_runs()

        for variant in [default_variant, *other_options.all()]:
            variant_runs = runs_qs.filter(variant.to_q_filter()).all()

            runs = []

            for variant_run in variant_runs:
                source_flag = "(Source)" if variant_run.is_source_run else ""
                runs.append(f"{variant_run.courseware_id}{source_flag}")

            runs = " ".join(runs) if len(runs) > 0 else self.style.WARNING("NO RUNS")

            self.stdout.write(
                f"Language = {variant.language} Industry = {variant.variant_industry} Length = {variant.variant_length}"
            )
            self.stdout.write(f"\t{runs}")
