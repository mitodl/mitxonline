"""Management command for B2B contracts."""

import logging

from django.core.management import BaseCommand, CommandError
from rich.console import Console
from rich.table import Table

from b2b.api import create_contract_run
from b2b.constants import CONTRACT_INTEGRATION_NONSSO, CONTRACT_INTEGRATION_SSO
from b2b.models import ContractPage, OrganizationIndexPage, OrganizationPage
from courses.api import resolve_courseware_object_from_id

log = logging.getLogger(__name__)


class Command(BaseCommand):
    """Manage B2B contracts."""

    help = "Manage B2B contracts."

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
        )

        list_parser = subparsers.add_parser(
            "list",
            help="List orgs and contracts.",
        )
        list_parser.add_argument(
            "type",
            type=str,
            help="The data to list.",
            choices=["organizations", "contracts", "users"],
            default="organizations",
        )
        list_parser.add_argument(
            "--org",
            "--organization",
            type=int,
            help="Filter by organization ID.",
            dest="organization_id",
        )
        list_parser.add_argument(
            "--contract",
            type=int,
            help="Filter by contract ID.",
            dest="contract_id",
        )

        create_parser = subparsers.add_parser(
            "create",
            help="Create a new contract.",
        )
        create_parser.add_argument(
            "organization",
            type=str,
            help="The name of the organization.",
        )
        create_parser.add_argument(
            "contract_name",
            type=str,
            help="The name of the contract.",
        )
        create_parser.add_argument(
            "integration_type",
            type=str,
            help="The type of integration for this contract.",
            choices=[
                CONTRACT_INTEGRATION_SSO,
                CONTRACT_INTEGRATION_NONSSO,
            ],
            default=CONTRACT_INTEGRATION_NONSSO,
        )
        create_parser.add_argument(
            "--description",
            type=str,
            help="Description of the contract.",
        )
        create_parser.add_argument(
            "--start",
            type=str,
            help="The start date of the contract.",
        )
        create_parser.add_argument(
            "--end",
            type=str,
            help="The end date of the contract.",
        )
        create_parser.add_argument(
            "--create",
            action="store_true",
            help="Create an organization if it does not exist.",
        )

        modify_parser = subparsers.add_parser(
            "modify",
            help="Modify an existing contract.",
        )
        modify_parser.add_argument(
            "contract_id",
            type=int,
            help="The ID of the contract to modify.",
        )
        modify_parser.add_argument(
            "--start",
            type=str,
            help="Change the start date of the contract.",
        )
        modify_parser.add_argument(
            "--end",
            type=str,
            help="Change the end date of the contract.",
        )
        modify_parser.add_argument(
            "--active",
            action="store_true",
            help="Set the contract as active.",
        )
        modify_parser.add_argument(
            "--inactive",
            "--delete",
            action="store_true",
            help="Set the contract as inactive.",
            dest="inactive",
        )

        courseware_parser = subparsers.add_parser(
            "courseware",
            help="Manage courseware assigned to a contract.",
        )
        courseware_parser.add_argument(
            "contract_id",
            type=int,
            help="The ID of the contract to courseware courseware to.",
        )
        courseware_parser.add_argument(
            "--remove",
            action="store_true",
            help="Remove courseware from the contract. (Default is to add.)",
            dest="remove",
        )
        courseware_parser.add_argument(
            "--no-create-runs",
            action="store_false",
            help="Don't create new runs for this contract.",
            dest="create_runs",
        )
        courseware_parser.add_argument(
            "courseware_id",
            type=str,
            help="The ID of the courseware to courseware.",
            action="append",
        )

        return super().add_arguments(parser)

    def handle_list(self, *args, **kwargs):  # noqa: ARG002
        """Handle the list subcommand."""
        data_type = kwargs.pop("type")
        org_id = kwargs.pop("organization_id")
        # contract_id = kwargs.pop("contract_id")

        console = Console()

        if data_type == "organizations":
            orgs = OrganizationPage.objects.all()

            org_table = Table(title="B2B Organizations")
            org_table.add_column("ID", justify="right")
            org_table.add_column("Name", justify="left")
            org_table.add_column("Contracts", justify="left")

            for org in orgs:
                org_table.add_row(
                    str(org.id),
                    str(org.name),
                    str(org.get_children().type(ContractPage).count()),
                )

            console.print(org_table)
        elif data_type == "contracts":
            if org_id:
                org = OrganizationPage.objects.filter(id=org_id).first()
                if not org:
                    msg = f"Organization with ID '{org_id}' does not exist."
                    raise CommandError(msg)

                contracts = org.get_children().type(ContractPage)
            else:
                contracts = ContractPage.objects.all()

            contract_table = Table(title="Contracts")
            contract_table.add_column("ID", justify="right")
            contract_table.add_column("Name", justify="left")
            contract_table.add_column("Org Name", justify="left")
            contract_table.add_column("Integration", justify="left")
            contract_table.add_column("Start", justify="left")
            contract_table.add_column("End", justify="left")
            contract_table.add_column("Active", justify="left")

            for contract in contracts:
                contract_table.add_row(
                    str(contract.id),
                    str(contract.name),
                    str(contract.organization.name),
                    str(contract.integration_type),
                    str(contract.contract_start),
                    str(contract.contract_end),
                    str(contract.active),
                )

            console.print(contract_table)
        elif data_type == "users":
            self.stdout.write("Listing users is not implemented yet.")

    def handle_create(self, *args, **kwargs):  # noqa: ARG002
        """Handle the create subcommand."""
        organization_name = kwargs.pop("organization")
        contract_name = kwargs.pop("contract_name")
        integration_type = kwargs.pop("integration_type")
        description = kwargs.pop("description")
        start_date = kwargs.pop("start")
        end_date = kwargs.pop("end")
        create_organization = kwargs.pop("create")

        self.stdout.write(
            f"Creating contract '{contract_name}' for organization '{organization_name}'"
        )

        org = OrganizationPage.objects.filter(name=organization_name).first()

        log.info("Got organization %s", org)

        if not org and create_organization:
            parent = OrganizationIndexPage.objects.first()
            org = OrganizationPage(name=organization_name)
            parent.add_child(instance=org)
            org.save()
            parent.save()
            org.refresh_from_db()
            self.stdout.write(f"Created organization '{organization_name}'")
        elif not org:
            msg = f"Organization '{organization_name}' does not exist. Use --create to create it."
            raise CommandError(msg)

        contract = ContractPage(
            name=contract_name,
            description=description or "",
            integration_type=integration_type,
            organization=org,
            contract_start=start_date,
            contract_end=end_date,
        )
        org.add_child(instance=contract)
        contract.save()
        self.stdout.write(
            f"Created contract '{contract_name}' for organization '{organization_name}'"
        )

    def handle_modify(self, *args, **kwargs):  # noqa: ARG002
        """Handle the modify subcommand."""
        contract_id = kwargs.pop("contract_id")
        start_date = kwargs.pop("start")
        end_date = kwargs.pop("end")
        active = kwargs.pop("active")
        inactive = kwargs.pop("inactive")

        contract = ContractPage.objects.filter(id=contract_id).first()
        if not contract:
            msg = f"Contract with ID '{contract_id}' does not exist."
            raise CommandError(msg)

        if start_date:
            contract.contract_start = start_date
        if end_date:
            contract.contract_end = end_date
        if active:
            contract.active = True
        if inactive:
            contract.active = False

        contract.save()
        self.stdout.write(f"Modified contract with ID '{contract_id}'")

    def handle_courseware(self, *args, **kwargs):  # noqa: ARG002, C901
        """Add/remove courseware in a contract."""
        contract_id = kwargs.pop("contract_id")
        remove = kwargs.pop("remove")
        create_runs = kwargs.pop("create_runs")
        courseware_ids = kwargs.pop("courseware_id")

        contract = ContractPage.objects.filter(id=contract_id).first()
        if not contract:
            msg = f"Contract with ID '{contract_id}' does not exist."
            raise CommandError(msg)

        managed = skipped = 0

        for courseware_id in courseware_ids:
            courseware = resolve_courseware_object_from_id(courseware_id)
            if not courseware:
                self.stdout.write(
                    self.style.ERROR(
                        f"Courseware with ID '{courseware_id}' does not exist, skipping."
                    )
                )
                skipped += 1
            elif courseware.is_program:
                # If you're specifying a program, we will always make new runs
                # since we won't be able to tell which existing ones to use.

                self.stdout.write(
                    self.style.WARNING(
                        f"'{courseware_id}' is a program, so creating runs for all of its courses."
                    )
                )

                for course, _ in courseware.courses:
                    if self.create_run(contract, course):
                        managed += 1
                    else:
                        skipped += 1
            elif courseware.is_run:
                # This run already exists, so just add/remove it.
                # - If the run is owned by a different contract, skip it.
                # - If remove is True, remove the run from the contract.
                # - If remove is False, add the run to the contract.

                if courseware.b2b_contract and courseware.b2b_contract != contract:
                    # Already owned by another contract, so skip
                    self.stdout.write(
                        self.style.WARNING(
                            f"Run '{courseware_id}' is already owned by {courseware.b2b_contract}."
                        )
                    )
                    skipped += 1
                    continue

                if remove:
                    # Remove the run from the contract
                    courseware.b2b_contract = None
                    courseware.save()
                    managed += 1
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
                f"Managed {managed} courseware items and skipped {skipped} courseware items for {len(courseware_ids)} specified courseware IDs."
            )
        )

    def handle(self, *args, **kwargs):  # noqa: ARG002
        """Handle the command."""
        subcommand = kwargs.pop("subcommand")
        if subcommand == "create":
            self.handle_create(**kwargs)
        elif subcommand == "modify":
            self.handle_modify(**kwargs)
        elif subcommand == "courseware":
            self.handle_courseware(**kwargs)
        elif subcommand == "list":
            self.handle_list(**kwargs)
        else:
            log.error("Unknown subcommand: %s", subcommand)
            return 1
        return 0
