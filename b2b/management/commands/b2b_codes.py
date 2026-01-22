"""Management command to work with B2B enrollment codes."""

import csv
import json
import logging
from pathlib import Path

from django.core.management import BaseCommand, CommandError
from django.db.models import Q
from rich.console import Console
from rich.table import Table

from b2b.models import ContractPage, DiscountContractAttachmentRedemption
from ecommerce.models import DiscountRedemption, OrderStatus

log = logging.getLogger(__name__)


class Command(BaseCommand):
    """Operations for B2B enrollment codes."""

    help = "Operations to manage B2B enrollment codes - check validity, create/update, etc."
    operations = [
        "check",
        "generate",
        "validate",
        "expire",
    ]
    output_options = [
        "fancy",
        "csv",
        "json",
    ]

    def _add_b2b_obj_args(self, parser):
        """Add B2B object arguments to the parser."""

        parser.add_argument(
            "--contract",
            help="The contract to manage (either ID or slug).",
            type=str,
        )
        parser.add_argument(
            "--organization",
            "--org",
            help="The organization to pull contracts to manage from (either ID, slug, or UUID).",
            type=str,
        )

    def _get_contract_list(self, *, allow_everything=False, **kwargs):
        """Get the contract list based on the arguments passed."""
        contracts = []

        contract_id = kwargs.pop("contract", False)
        org_id = kwargs.pop("organization", False)
        if contract_id:
            if contract_id.isdecimal():
                contracts = ContractPage.objects.filter(id=contract_id).all()
            else:
                contracts = ContractPage.objects.filter(slug=contract_id).all()

            if contracts.count() > 1:
                self.stdout.write(
                    self.style.WARNING(
                        f"WARNING: Identifier {contract_id} returned >1 contract!"
                    )
                )

            if contracts.count() == 0:
                msg = f"Identifier {contract_id} not found."
                raise CommandError(msg)
        elif org_id:
            if org_id.isdecimal():
                contracts = ContractPage.objects.filter(organization__id=org_id).all()
            else:
                contracts = ContractPage.objects.filter(
                    Q(organization__slug=org_id)
                    | Q(organization__sso_organization_id=org_id)
                ).all()
        elif allow_everything:
            self.stdout.write(
                self.style.WARNING(
                    "No contract or org specified - returning all contracts."
                )
            )
            contracts = ContractPage.objects.all()

        if len(contracts) == 0:
            self.stdout.write(self.style.WARNING("No contracts found."))

        return contracts

    def _output_code_data(
        self, output_format, output_data, *, filename=None, table_name="Table"
    ):
        """Handle the output for the check command."""

        if output_format not in ["csv", "json"]:
            # Output using Rich - this goes straight to the console.
            console = Console()
            table = Table(title=table_name)

            for col_name in output_data[0]:
                table.add_column(col_name)

            for row in output_data:
                table.add_row(*row.values())

            console.print(table)
            return

        with Path(filename).open("w+") if filename else self.stdout as outfile:
            if output_format == "json":
                json.dump(output_data, outfile)
            else:
                writer = csv.DictWriter(outfile, output_data[0].keys())

                writer.writeheader()
                for row in output_data:
                    writer.writerow(row)

        if filename:
            self.stdout.write(
                self.style.SUCCESS(f"Wrote {output_format} output to {filename}.")
            )

    def _output_contract_stats_table(self, contract):
        """Gather stats on code usage for the specified contract."""

        usage_data = {
            "Seat Limit": str(contract.max_learners)
            if contract.max_learners
            else "Unlim",
            "Attachments": str(contract.get_learners().count()),
            "Run Count": str(contract.get_course_runs().count()),
            "Enrollments": str(contract.get_enrollments().count()),
            "Total Codes": str(contract.get_discounts().count()),
            "Redeemed for Attachment": str(0),
            "Redeemed for Enrollment": str(0),
        }

        usage_data["Redeemed for Enrollment"] = str(
            DiscountRedemption.objects.filter(
                redeemed_discount__in=contract.get_discounts(),
                redeemed_order__state=OrderStatus.FULFILLED,
            ).count()
        )
        usage_data["Redeemed for Attachment"] = str(
            DiscountContractAttachmentRedemption.objects.filter(
                contract=contract
            ).count()
        )

        self._output_code_data(
            "fancy", [usage_data], table_name=f"Stats for {contract}"
        )

        if contract.max_learners and contract.is_overfull():
            self.stdout.write(
                self.style.ERROR(f"Contract {contract} is overcommitted.")
            )

    def handle_output(self, **kwargs):
        """Output code information."""

        contracts = self._get_contract_list(allow_everything=True, **kwargs)

        if kwargs.pop("stats", False):
            # Display usage for the contract(s). This is basically an overview
            # report.

            self.stdout.write(f"Generating stats for {len(contracts)} contracts...")

            for contract in contracts:
                self._output_contract_stats_table(contract)

            return

        if kwargs.pop("usage", False):
            # Display just code redemptions per contract.
            # This will be one big table with a flag specifying if the code is
            # used for attach or enroll. Codes may be listed twice because they
            # may be used for attach _and_ enroll.

            code_usage = []

            for contract in contracts:
                attachments = [
                    {
                        "Contract": str(contract),
                        "Code": str(dcar.discount.discount_code),
                        "Redeemed By": str(dcar.user.email),
                        "Redemption Date": str(dcar.created_on),
                        "Type": "attach",
                    }
                    for dcar in DiscountContractAttachmentRedemption.objects.prefetch_related(
                        "discount", "user"
                    )
                    .filter(contract=contract)
                    .all()
                ]
                enrollments = [
                    {
                        "Contract": str(contract),
                        "Code": str(dr.redeemed_discount.discount_code),
                        "Redeemed By": str(dr.redeemed_by.email),
                        "Redemption Date": str(dr.redemption_date),
                        "Type": "enroll",
                    }
                    for dr in DiscountRedemption.objects.prefetch_related(
                        "redeemed_discount", "redeemed_by"
                    )
                    .filter(redeemed_discount__in=contract.get_discounts())
                    .all()
                ]
                code_usage.extend(attachments)
                code_usage.extend(enrollments)

            self._output_code_data(
                kwargs.pop("output_format", "fancy"),
                code_usage,
                filename=kwargs.pop("filename", None),
                table_name="Code Usage",
            )

        # If usage or stats flags aren't set, list out the codes.
        # Codes will be listed for attachment to the contract.
        # - If the "all" flag is set, then we output all the codes along with the
        #   course runs they belong to, with flags for usage for attachment or
        #   enrollment.
        # - Otherwise, only an appropriate number of codes is gathered that have
        #   not been used yet. If the contract has a learner limit, only a sufficient
        #   number of codes to fill the contract will be delivered. (e.g. for 100
        #   seats, 19 occupied, you'd get back 81 codes.)

    def handle_validate(self):
        """Validate and fix enrollment codes."""

    def handle_expire(self):
        """Expire enrollment codes."""

    def add_arguments(self, parser):
        """Add arguments to the command."""

        subparser = parser.add_subparsers(
            title="Operation",
            help="The operation to perform.",
            dest="operation",
        )

        output_parser = subparser.add_parser(
            "output",
            help="Output enrollment codes for a contract or organization.",
        )
        validate_parser = subparser.add_parser(
            "validate",
            help="Validate and fix enrollment codes for a contract or organization.",
            aliases=[
                "fix",
                "check",
            ],
        )
        expire_parser = subparser.add_parser(
            "expire",
            help="Expire enrollment codes for a contract or organization, optionally creating new ones.",
        )

        self._add_b2b_obj_args(output_parser)
        self._add_b2b_obj_args(validate_parser)
        self._add_b2b_obj_args(expire_parser)

        output_parser.add_argument(
            "--format",
            type=str,
            default="fancy",
            choices=self.output_options,
            help="Output format (json, csv, fancy) (not for stats).",
            dest="output_format",
        )
        output_parser.add_argument(
            "--filename", type=str, help="Output to file (not for stats)."
        )
        output_parser.add_argument(
            "--stats",
            action="store_true",
            help="Output statistics about code usage.",
        )
        output_parser.add_argument(
            "--usage",
            action="store_true",
            help="Output redemptions/usage for codes.",
        )

        validate_parser.add_argument(
            "--fix",
            help="Fix the codes - otherwise, this will just tell you if the code set is invalid.",
            action="store_true",
        )

        expire_parser.add_argument(
            "--expire",
            help="Expire the codes without prompting.",
            action="store_true",
        )

    def handle(self, *args, **kwargs):
        """Dispatch the requested subcommand."""

        op = kwargs.pop("operation")

        if op == "output":
            self.handle_output(*args, **kwargs)
        elif op == "validate":
            self.handle_validate()
        elif op == "expire":
            self.handle_expire()
        else:
            msg = f"Invalid subcommand {op}"
            raise CommandError(msg)
