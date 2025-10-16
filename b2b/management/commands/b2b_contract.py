"""Management command for B2B contracts."""

import logging
from decimal import Decimal

from django.core.management import BaseCommand, CommandError
from django.db.models import Q

from b2b.constants import (
    CONTRACT_MEMBERSHIP_CHOICES,
)
from b2b.models import ContractPage, OrganizationIndexPage, OrganizationPage

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
            help="The name (or org key) of the organization.",
        )
        create_parser.add_argument(
            "contract_name",
            type=str,
            help="The name of the contract.",
        )
        create_parser.add_argument(
            "integration_type",
            type=str,
            help="The membership type for this contract.",
            choices=[value[0] for value in CONTRACT_MEMBERSHIP_CHOICES],
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
        create_parser.add_argument(
            "--org-key",
            type=str,
            help="The org key to use for the new organization.",
        )
        create_parser.add_argument(
            "--max-learners",
            type=int,
            help="The maximum number of learners for this contract.",
            default=None,
        )
        create_parser.add_argument(
            "--price",
            type=Decimal,
            help="The fixed price for enrollment under this contract.",
            default=None,
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
        modify_parser.add_argument(
            "--max-learners",
            type=int,
            help="The maximum number of learners for this contract.",
            default=None,
        )
        modify_parser.add_argument(
            "--price",
            type=Decimal,
            help="The fixed price for enrollment under this contract.",
            default=None,
        )
        modify_parser.add_argument(
            "--no-price",
            action="store_true",
            help="Clear the price for this contract (makes enrollments free).",
        )
        modify_parser.add_argument(
            "--no-learner-cap",
            action="store_true",
            help="Clear the learner limit.",
        )
        modify_parser.add_argument(
            "--no-start-date",
            action="store_true",
            help="Clear the start date.",
        )
        modify_parser.add_argument(
            "--no-end-date",
            action="store_true",
            help="Clear the end date.",
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
        max_learners = kwargs.pop("max_learners")
        price = kwargs.pop("price")
        new_org_key = kwargs.pop("org_key")

        self.stdout.write(
            f"Creating contract '{contract_name}' for organization '{organization_name}'"
        )

        org = OrganizationPage.objects.filter(
            Q(name=organization_name) | Q(org_key=organization_name)
        ).first()

        log.info("Got organization %s", org)

        if not org and create_organization:
            if not new_org_key:
                msg = f"To create '{organization_name}', you must supply an org key."
                raise CommandError(msg)

            parent = OrganizationIndexPage.objects.first()
            org = OrganizationPage(name=organization_name, org_key=new_org_key)
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
            membership_type=integration_type,
            organization=org,
            contract_start=start_date,
            contract_end=end_date,
            max_learners=max_learners,
            enrollment_fixed_price=price,
        )
        org.add_child(instance=contract)
        contract.save()
        self.stdout.write(
            f"Created contract '{contract_name}' for organization '{organization_name}'"
        )

    def handle_modify(self, *args, **kwargs):  # noqa: ARG002, C901
        """Handle the modify subcommand."""
        contract_id = kwargs.pop("contract_id")
        start_date = kwargs.pop("start")
        end_date = kwargs.pop("end")
        active = kwargs.pop("active")
        inactive = kwargs.pop("inactive")
        max_learners = kwargs.pop("max_learners")
        price = kwargs.pop("price")
        no_price = kwargs.pop("no_price")
        no_learner_cap = kwargs.pop("no_learner_cap")
        no_start_date = kwargs.pop("no_start_date")
        no_end_date = kwargs.pop("no_end_date")

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
        if max_learners is not None:
            contract.max_learners = max_learners
        if price is not None:
            contract.enrollment_fixed_price = price

        if no_price:
            contract.enrollment_fixed_price = None
        if no_learner_cap:
            contract.max_learners = None
        if no_start_date:
            contract.contract_start = None
        if no_end_date:
            contract.contract_end = None

        contract.save()
        self.stdout.write(f"Modified contract with ID '{contract_id}'")

    def handle(self, *args, **kwargs):  # noqa: ARG002
        """Handle the command."""
        subcommand = kwargs.pop("subcommand")
        if subcommand == "create":
            self.handle_create(**kwargs)
        elif subcommand == "modify":
            self.handle_modify(**kwargs)
        else:
            log.error("Unknown subcommand: %s", subcommand)
            return 1
        return 0
