"""Management command for B2B contracts."""

import logging
from argparse import ArgumentError

from django.core.management import BaseCommand

from b2b.constants import CONTRACT_INTEGRATION_NONSSO
from b2b.models import ContractPage, OrganizationPage
from courses.api import resolve_courseware_object_from_id

log = logging.getLogger(__name__)


class Command(BaseCommand):
    """Manage B2B contracts."""

    help = "Manage B2B contracts."

    def add_arguments(self, parser):
        """Add command line arguments."""

        subparsers = parser.add_subparsers(
            title="Task",
            dest="subcommand",
            required=True,
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
            "--create-runs",
            action="store_true",
            help="Create runs if applicable (i.e., not for programs or existing runs).",
            dest="create_runs",
        )
        courseware_parser.add_argument(
            "courseware_id",
            type=str,
            help="The ID of the courseware to courseware.",
            action="append",
        )

        return super().add_arguments(parser)

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
        if not org and create_organization:
            org = OrganizationPage(name=organization_name)
            org.save()
            self.stdout.write(f"Created organization '{organization_name}'")
        elif not org:
            msg = f"Organization '{organization_name}' does not exist. Use --create to create it."
            raise ArgumentError(msg)

        contract = ContractPage(
            name=contract_name,
            description=description,
            integration_type=integration_type,
            organization=org,
            contract_start=start_date,
            contract_end=end_date,
        )
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
            raise ArgumentError(msg)

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

    def handle_courseware(self, *args, **kwargs):  # noqa: ARG002
        """Add/remove courseware in a contract."""
        contract_id = kwargs.pop("contract_id")
        remove = kwargs.pop("remove")
        create_runs = kwargs.pop("create_runs")
        courseware_ids = kwargs.pop("courseware_id")

        contract = ContractPage.objects.filter(id=contract_id).first()
        if not contract:
            msg = f"Contract with ID '{contract_id}' does not exist."
            raise ArgumentError(msg)

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
                continue

            if courseware.is_program:
                # TODO: we should grab the associated courses and add runs
                # skipping for now to make sure course adding is OK
                self.stdout.write(
                    self.style.ERROR(
                        f"Courseware with ID '{courseware_id}' is a program, skipping."
                    )
                )
                skipped += 1
                continue

            if courseware.is_run:
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
            else:
                # Create the run and attach it to the contract.
                # This should also create the run in edX.
                managed += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Managed {managed} courseware items and skipped {skipped} courseware items."
            )
        )

    def handle(self, *args, **kwargs):  # noqa: ARG002
        """Handle the command."""
        subcommand = kwargs.pop("subcommand")
        if subcommand == "create":
            self.handle_create(**kwargs)
        elif subcommand == "modify":
            self.stdout.write("self.modify_contract(**kwargs)")
        elif subcommand == "courseware":
            self.stdout.write("self.courseware_courseware(**kwargs)")
        else:
            log.error("Unknown subcommand: %s", subcommand)
            return 1
        return 0
