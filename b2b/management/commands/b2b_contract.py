"""Management command for B2B contracts."""

import logging
from decimal import Decimal

from django.core.management import BaseCommand, CommandError
from django.db.models import Q

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
        create_parser.add_argument(
            "--org-key",
            type=str,
            help="The org key to use for the new organization.",
        )
        create_parser.add_argument(
            "--org-uuid",
            type=str,
            help="The org UUID to use for the new organization.",
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
        new_org_uuid = kwargs.pop("org_uuid")

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
            org = OrganizationPage(
                name=organization_name,
                org_key=new_org_key,
                sso_organization_id=new_org_uuid,
            )
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
            elif remove:
                # If we're removing courseware, skip it if it's not a run.
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipping removal of courseware '{courseware_id}' for contract {contract} because it is not a run. Removals must specify runs."
                    )
                )
                skipped += 1
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
        else:
            log.error("Unknown subcommand: %s", subcommand)
            return 1
        return 0
