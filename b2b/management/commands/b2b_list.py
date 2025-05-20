"""List B2B data."""

import csv
import logging
from pathlib import Path
from urllib.parse import urlencode, urljoin

from django.conf import settings
from django.core.management import BaseCommand, CommandError
from django.urls import reverse
from rich.console import Console
from rich.table import Table

from b2b.models import ContractPage, OrganizationPage
from courses.models import CourseRun

log = logging.getLogger(__name__)


class Command(BaseCommand):
    """List B2B data."""

    help = "List B2B data."

    def _fmt_redemptions(self, code):
        """Format the redemptions for a code."""

        if code.order_redemptions.count() == 0:
            return "No"
        elif code.order_redemptions.count() == 1:
            return code.order_redemptions.first().redemeed_by.email

        return code.order_redemptions.count()

    def _gen_product_url(self, product):
        """Generate the product URL."""

        qs = urlencode(
            {
                "product_id": product.id,
            }
        )

        return urljoin(
            settings.SITE_BASE_URL,
            urljoin(
                reverse("checkout-product"),
                f"?{qs}",
            ),
        )

    def add_arguments(self, parser):
        """Add command line arguments."""

        subparsers = parser.add_subparsers(
            title="Data type",
            dest="subcommand",
            required=True,
        )

        org_parser = subparsers.add_parser(
            "organizations",
            help="List organization data.",
        )
        org_parser.add_argument(
            "--org",
            "--organization",
            type=int,
            help="Filter by organization ID.",
            dest="organization_id",
        )

        contract_parser = subparsers.add_parser(
            "contracts",
            help="List contract data.",
        )
        contract_parser.add_argument(
            "--org",
            "--organization",
            type=int,
            help="Filter by organization ID.",
            dest="organization_id",
        )
        contract_parser.add_argument(
            "--codes",
            type=int,
            help="List enrollment codes for the specified contract.",
        )
        contract_parser.add_argument(
            "--codes-out",
            type=str,
            help="Output file for enrollment codes.",
            default="",
        )

        courseware_parser = subparsers.add_parser(
            "courseware",
            help="List associated courseware data.",
        )
        courseware_parser.add_argument(
            "--org",
            "--organization",
            type=int,
            help="Filter by organization ID.",
            dest="organization_id",
        )
        courseware_parser.add_argument(
            "--contract",
            type=int,
            help="Filter by contract ID.",
            dest="contract_id",
        )

        learners_parser = subparsers.add_parser(
            "learners",
            help="List learners associated with an org or contract.",
        )
        learners_parser.add_argument(
            "--org",
            "--organization",
            type=int,
            help="Filter by organization ID.",
            dest="organization_id",
        )
        learners_parser.add_argument(
            "--contract",
            type=int,
            help="Filter by contract ID.",
            dest="contract_id",
        )

        return super().add_arguments(parser)

    def handle_list_orgs(self, *args, **kwargs):  # noqa: ARG002
        """Handle the list subcommand."""
        org_id = kwargs.pop("organization_id")

        if org_id:
            orgs = OrganizationPage.objects.filter(id=org_id).all()
        else:
            orgs = OrganizationPage.objects.all()

        org_table = Table(title="B2B Organizations")
        org_table.add_column("ID", justify="right")
        org_table.add_column("Name", justify="left")
        org_table.add_column("Slug", justify="left")
        org_table.add_column("Contracts", justify="left")

        for org in orgs:
            org_table.add_row(
                str(org.id),
                org.name,
                org.slug,
                str(org.get_children().type(ContractPage).count()),
            )

        self.console.print(org_table)

    def handle_list_contracts(self, *args, **kwargs):  # noqa: ARG002
        """Handle the list subcommand."""
        org_id = kwargs.pop("organization_id")
        codes_contract_id = kwargs.pop("codes")

        if codes_contract_id:
            output_file = kwargs.pop("codes_out")
            if not output_file:
                output_file = f"codes-{codes_contract_id}.csv"
            contract = ContractPage.objects.get(id=codes_contract_id)

            with Path(output_file).open("w") as f:
                csv_writer = csv.writer(f)
                csv_writer.writerow(
                    [
                        "Code",
                        "Product",
                        "Redeemed",
                        "Product URL",
                    ]
                )

                for code in contract.get_discounts():
                    csv_writer.writerow(
                        [
                            code.discount_code,
                            code.products.first().product,
                            self._fmt_redemptions(code),
                            self._gen_product_url(code.products.first().product),
                        ]
                    )

            self.stdout.write(self.style.SUCCESS(f"Codes written to {output_file}"))
            return

        if org_id:
            contracts = ContractPage.objects.filter(organization__id=org_id).all()
        else:
            contracts = ContractPage.objects.all()

        contract_table = Table(title="Contracts")
        contract_table.add_column("ID", justify="right")
        contract_table.add_column("Name", justify="left")
        contract_table.add_column("Slug", justify="left")
        contract_table.add_column("Org Name", justify="left")
        contract_table.add_column("Integration", justify="left")
        contract_table.add_column("Start", justify="left")
        contract_table.add_column("End", justify="left")
        contract_table.add_column("Active", justify="left")
        contract_table.add_column("Max Learners", justify="left")
        contract_table.add_column("Price", justify="left")

        for contract in contracts:
            contract_table.add_row(
                str(contract.id),
                contract.name,
                contract.slug,
                contract.organization.name,
                contract.integration_type,
                contract.contract_start.strftime("%Y-%m-%d\n%H:%M")
                if contract.contract_start
                else "",
                contract.contract_end.strftime("%Y-%m-%d\n%H:%M")
                if contract.contract_end
                else "",
                "Yes" if contract.active else "No",
                str(contract.max_learners) if contract.max_learners else "Unlim",
                str(contract.enrollment_fixed_price)
                if contract.enrollment_fixed_price
                else "",
            )

        self.console.print(contract_table)

    def handle_list_courseware(self, *args, **kwargs):  # noqa: ARG002
        """Handle the list subcommand."""
        org_id = kwargs.pop("organization_id")
        contract_id = kwargs.pop("contract_id")

        # We only link course runs to contracts. This will need to be updated
        # if we ever have other types (like program runs or something).

        contract_page_qs = ContractPage.objects

        if org_id:
            contract_page_qs = contract_page_qs.filter(
                organization__id=org_id,
            )

        if contract_id:
            contract_page_qs = contract_page_qs.filter(id=contract_id)

        contracts = contract_page_qs.all()

        courseware = (
            CourseRun.objects.prefetch_related("b2b_contract")
            .filter(b2b_contract__in=contracts)
            .all()
        )

        courseware_table = Table(title="Courseware")
        courseware_table.add_column("ID", justify="right")
        courseware_table.add_column("Org/Contract", justify="left")
        courseware_table.add_column("Type", justify="left")
        courseware_table.add_column("Readable ID", justify="left", no_wrap=True)
        courseware_table.add_column("Name", justify="left")
        courseware_table.add_column("Start", justify="left")
        courseware_table.add_column("End", justify="left")

        for cw in courseware:
            courseware_table.add_row(
                str(cw.id),
                f"{cw.b2b_contract.organization.name}\n{cw.b2b_contract.name}",
                "CR",
                cw.readable_id,
                cw.title,
                cw.start_date.strftime("%Y-%m-%d\n%H:%M") if cw.start_date else "",
                cw.end_date.strftime("%Y-%m-%d\n%H:%M") if cw.end_date else "",
            )

        self.console.print(courseware_table)

    def handle_list_learners(self, *args, **kwargs):  # noqa: ARG002
        """List learners associated with an org or contract."""

        org_id = kwargs.pop("organization_id")
        contract_id = kwargs.pop("contract_id")

        if org_id:
            obj = OrganizationPage.objects.get(id=org_id)
        elif contract_id:
            obj = ContractPage.objects.get(id=contract_id)
        else:
            msg = "Must provide either org or contract ID."
            raise CommandError(msg)

        learners = obj.get_learners()

        learners_table = Table(title=f"Learners for {obj}")
        learners_table.add_column("Email", justify="right")
        learners_table.add_column("Name", justify="left")

        for learner in learners:
            learners_table.add_row(
                learner.email,
                f"{learner.first_name} {learner.last_name}",
            )
        self.console.print(learners_table)

    def handle(self, *args, **kwargs):  # noqa: ARG002
        """Handle the command."""
        self.console = Console()
        subcommand = kwargs.pop("subcommand")
        if subcommand == "organizations":
            self.handle_list_orgs(**kwargs)
        elif subcommand == "contracts":
            self.handle_list_contracts(**kwargs)
        elif subcommand == "courseware":
            self.handle_list_courseware(**kwargs)
        elif subcommand == "learners":
            self.handle_list_learners(**kwargs)
        else:
            msg = f"Unknown subcommand: {subcommand}"
            raise CommandError(msg)

        return 0
