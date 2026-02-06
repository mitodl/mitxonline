"""Management command to work with B2B enrollment codes."""

import csv
import json
import logging
import uuid
from pathlib import Path

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.management import BaseCommand, CommandError
from django.db.models import Count, Q
from rich.console import Console
from rich.table import Table

from b2b.api import (
    ensure_contract_run_pricing,
    ensure_contract_run_products,
    ensure_enrollment_codes_exist,
    get_contract_products_with_bad_pricing,
    get_contract_runs_without_products,
)
from b2b.constants import CONTRACT_MEMBERSHIP_AUTOS
from b2b.models import ContractPage, DiscountContractAttachmentRedemption
from courses.models import CourseRun
from ecommerce.constants import REDEMPTION_TYPE_ONE_TIME, REDEMPTION_TYPE_UNLIMITED
from ecommerce.models import Discount, DiscountRedemption, OrderStatus

log = logging.getLogger(__name__)


def is_valid_uuid(test_uuid: str) -> bool:
    """Determine if the string is a UUID or not."""

    try:
        uuid.UUID(str(test_uuid))
    except ValueError:
        return False

    return True


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
            self.stdout.write(f"Filtering by contract: {contract_id}")
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
            self.stdout.write(f"Filtering by organization: {org_id}")
            if org_id.isdecimal():
                contracts = ContractPage.objects.filter(organization__id=org_id).all()
            elif is_valid_uuid(org_id):
                contracts = ContractPage.objects.filter(
                    organization__sso_organization_id=org_id
                ).all()
            else:
                contracts = ContractPage.objects.filter(
                    Q(organization__slug=org_id) | Q(organization__org_key=org_id)
                ).all()
        elif allow_everything:
            self.stdout.write(
                self.style.WARNING(
                    "No contract or org specified - operating on all contracts."
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

        if len(output_data) == 0:
            self.stdout.write(self.style.ERROR("Nothing to output."))
            return

        if output_format not in ["csv", "json"]:
            # Output using Rich - this goes straight to the console.
            console = Console()
            table = Table(title=table_name)

            for col_name in output_data[0]:
                table.add_column(col_name, overflow="fold")

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

    def _format_enrollment_codes(
        self, contract, discounts, *, include_redemption_info=True
    ):
        """Format the enrollment codes for output."""

        codes = []
        content_type = ContentType.objects.get_for_model(CourseRun)
        contract_products = contract.get_products()

        for discount in discounts:
            code = {
                "Contract": str(contract),
                "Course Run": "",
                "Enrollment Code": discount.discount_code,
                "Attach Redemption": "",
                "Enroll Redemption": "",
                "Attach Link": f"{settings.MIT_LEARN_ATTACH_URL}{discount.discount_code}/",
            }

            if include_redemption_info:
                attach_qs = discount.contract_redemptions.filter(contract=contract)
                if attach_qs.count():
                    code["Attach Redemption"] = ",".join(
                        [dcr.user.email for dcr in attach_qs.all()]
                    )

                enroll_qs = discount.order_redemptions
                if enroll_qs.count():
                    code["Enroll Redemption"] = ",".join(
                        [ecr.redeemed_by.email for ecr in enroll_qs.all()]
                    )

            codes.extend(
                [
                    {**code, "Course Run": dp.product.purchasable_object.courseware_id}
                    for dp in discount.products.filter(
                        product__content_type=content_type,
                        product__in=contract_products,
                    ).all()
                ]
            )

        return codes

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

            return

        # If usage or stats flags aren't set, list out the codes.
        # Codes will be listed for attachment to the contract.
        # - If the "all" flag is set, then we output all the codes along with the
        #   course runs they belong to, with flags for usage for attachment or
        #   enrollment.
        # - Otherwise, only an appropriate number of codes is gathered that have
        #   not been used yet. If the contract has a learner limit, only a sufficient
        #   number of codes to fill the contract will be delivered. (e.g. for 100
        #   seats, 19 occupied, you'd get back 81 codes.)

        codes = []
        include_redemption_info = kwargs.pop("include_redemption_info", True)

        if kwargs.pop("all", False):
            for contract in contracts:
                codes.extend(
                    self._format_enrollment_codes(contract, contract.get_discounts())
                )

            self._output_code_data(
                kwargs.pop("output_format", "fancy"),
                codes,
                table_name="Enrollment Codes",
                filename=kwargs.pop("filename", None),
            )

            return

        for contract in contracts:
            remaining_discounts = 1

            if contract.max_learners:
                attached_learner_count = contract.get_learners().count()
                remaining_discounts = contract.max_learners - attached_learner_count

            annotated_discounts = (
                contract.get_discounts()
                .annotate(Count("contract_redemptions"))
                .filter(contract_redemptions__count=0)
                .all()[:remaining_discounts]
            )

            codes.extend(
                self._format_enrollment_codes(
                    contract,
                    annotated_discounts,
                    include_redemption_info=include_redemption_info,
                )
            )

        self._output_code_data(
            kwargs.pop("output_format", "fancy"),
            codes,
            table_name="Enrollment Codes",
            filename=kwargs.pop("filename", None),
        )

        return

    def handle_validate(self, **kwargs):
        """Validate and fix enrollment codes."""

        contracts = self._get_contract_list(**kwargs, allow_everything=False)

        for contract in contracts:
            self.stdout.write(f"Contract {contract} is type {contract.membership_type}")

            # Step 1: check for products for the associated course runs

            if get_contract_runs_without_products(contract).count() > 0:
                self.stdout.write(
                    self.style.WARNING(
                        f"Contract {contract} has associated course runs that are missing products."
                    )
                )

                new_products = ensure_contract_run_products(contract)

                self.stdout.write(
                    self.style.SUCCESS(f"Added {len(new_products)} products.")
                )

            # Step 2: make sure the products have the right pricing

            if get_contract_products_with_bad_pricing(contract).count() > 0:
                self.stdout.write(
                    self.style.WARNING(
                        f"Contract {contract} has course runs with products that have incorrect pricing."
                    )
                )

                fixed_products = ensure_contract_run_pricing(contract)

                self.stdout.write(
                    self.style.SUCCESS(f"Updated {fixed_products} products.")
                )

            # Step 3: check if the contract should have codes

            if (
                contract.membership_type in CONTRACT_MEMBERSHIP_AUTOS
                and not contract.enrollment_fixed_price
            ):
                # This is a managed contract with no price - people are added to
                # this automatically, so there shouldn't be any unredeemed codes.

                # Step 4: remove any unused codes, since we shouldn't have any.
                # There may be redeemed codes, because this contract may have
                # changed types or prices at some point. Those are left alone.

                total_codes = contract.get_discounts()
                unredeemed_codes = contract.get_unused_discounts()

                if total_codes.count() > unredeemed_codes.count():
                    self.stdout.write(
                        self.style.WARNING(
                            f"Contract {contract} has too many codes: {unredeemed_codes.count()} available out of {total_codes.count()} total, expecting 0."
                        )
                    )

                    removed_codes = ",".join(
                        [code.discount_code for code in unredeemed_codes]
                    )

                    # Remove unredeemed codes.
                    unredeemed_codes.delete()
                    self.stdout.write(
                        self.style.SUCCESS(f"Removed codes: {removed_codes}")
                    )
            else:
                # This contract requires enrollment codes. Check to make sure
                # we have the proper amount and that they're set up correctly.

                # Step 4: figure out what codes should be there

                expected_amount = (
                    0
                    if not contract.enrollment_fixed_price
                    else contract.enrollment_fixed_price
                )

                if contract.max_learners:
                    expected_codes_count = (
                        contract.max_learners * contract.get_course_runs().count()
                    )
                    code_redemption_type = REDEMPTION_TYPE_ONE_TIME
                else:
                    expected_codes_count = contract.get_course_runs().count()
                    code_redemption_type = REDEMPTION_TYPE_UNLIMITED

                total_code_count = contract.get_discounts().count()

                self.stdout.write(
                    f"Found {total_code_count} enrollment codes, expected {expected_codes_count}"
                )

                if expected_codes_count != total_code_count:
                    # We either have too many or too few codes.
                    self.stdout.write(
                        self.style.WARNING(
                            f"Code count for {contract} is not what is expected: expected {expected_codes_count}, got {total_code_count}"
                        )
                    )

                    ensure_enrollment_codes_exist(contract)

                # Step 5: make sure the codes are the right type and amount

                bad_settings_codes_qs = contract.get_discounts().exclude(
                    redemption_type=code_redemption_type, amount=expected_amount
                )

                if bad_settings_codes_qs.count() > 0:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Contract {contract} has {bad_settings_codes_qs.count()} codes with bad settings"
                        )
                    )

                    bad_codes = bad_settings_codes_qs.all()

                    for code in bad_codes:
                        code.redemption_type = code_redemption_type
                        code.amount = expected_amount

                    updated_count = Discount.objects.bulk_update(
                        bad_codes, ["redemption_type", "amount"]
                    )

                    self.stdout.write(f"Updated {updated_count} codes.")

        self.stdout.write(self.style.SUCCESS(f"Checked {len(contracts)} contracts."))

    def handle_expire(self, **kwargs):
        """Expire (delete) unused enrollment codes."""

        contracts = self._get_contract_list(**kwargs, allow_everything=False)
        dry_run = kwargs.pop("expire", True)

        if len(contracts) > 0:
            self.stdout.write(
                self.style.WARNING(
                    f"WARNING: Expiring codes from {len(contracts)} contracts."
                )
            )

        if not dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "WARNING: Expire mode active - will deactivate/delete codes."
                )
            )

        removed_codes = []

        for contract in contracts:
            discounts = contract.get_unused_discounts()
            contract_products = contract.get_products().all()

            for discount in discounts:
                code = [
                    str(contract),
                    discount.discount_code,
                    "detached",
                ]

                if not dry_run:
                    discount.products.filter(product__in=contract_products).delete()
                if discount.products.count() == (1 if dry_run else 0):
                    if not dry_run:
                        discount.delete()
                    code[2] = "deleted"

                removed_codes.append(code)

        self.stdout.write(self.style.SUCCESS(f"{len(removed_codes)} codes removed."))

        [self.stdout.write(",".join(code)) for code in removed_codes]

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
        output_parser.add_argument(
            "--all",
            action="store_true",
            help="Output all codes, rather than a usable subset.",
        )
        output_parser.add_argument(
            "--no-redemptions",
            default=True,
            action="store_false",
            dest="include_redemption_info",
            help="Don't include user data for code redemptions. (Cleaner output for sending to clients. Does not apply to --all.)",
        )

        validate_parser.add_argument(
            "--fix",
            help="Fix the codes - otherwise, this will just tell you if the code set is invalid.",
            action="store_true",
        )

        expire_parser.add_argument(
            "--expire",
            help="Actually expire the codes. (Default is to not make changes.)",
            action="store_false",
            default=True,
        )

    def handle(self, *args, **kwargs):
        """Dispatch the requested subcommand."""

        op = kwargs.pop("operation")

        if op == "output":
            self.handle_output(*args, **kwargs)
        elif op in ["validate", "fix", "check"]:
            self.handle_validate(*args, **kwargs)
        elif op == "expire":
            self.handle_expire(*args, **kwargs)
        else:
            msg = f"Invalid subcommand {op}"
            raise CommandError(msg)
