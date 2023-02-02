"""
Ensures there's a basic set of records present for financial assistance to work
for DEDP (or other) courses. This includes:
- A program (required for the tiers to be set up)
- A set of discounts, specific to the program
- Tiers that are tied to these discounts

The defaults for this are intended for use with DEDP and are:

Program:
- Readable ID is `program-v1:MITx+DEDP`
- Name is `Data, Economics and Development Policy`

Discounts: (year is the current year)
Code               | Type        | Amount
-----------------------------------------
DEDP-fa-tier1-year | dollars-off | 750
DEDP-fa-tier2-year | dollars-off | 650
DEDP-fa-tier3-year | dollars-off | 500
DEDP-fa-tier4-year | percent-off | 0
-----------------------------------------

Tiers:
Threshold | Discount
------------------------------
0         | DEDP-fa-tier1-year
25,000    | DEDP-fa-tier2-year
50,000    | DEDP-fa-tier3-year
75,000    | DEDP-fa-tier4-year
------------------------------

If discounts and tiers exist for the current year, this command will leave them
alone. If they exist for prior years, they will be disabled (current=False for
tiers and expiration date set to the past for discounts).

If a program exists with the readable ID specified, that will be used.

The defaults can be changed:
- Specify --program <courseware-id> to use a different program (this will be
created if it's not there already)
- Specify --program-name "<name>" to use a different program name (required if
you specify --program)
- Specify --program-abbrev "<abbreviation>" to use a different program
abbreviation in the discount codes (defaults to DEDP, required if you specify
--program)
- Specify --tier-info <filename> to set different tier levels. This expects a
CSV file with "threshold amount,discount type,discount amount" as the data set.
(Do not provide a header row.) Discount type should be "percent-off",
"dollars-off", or "fixed-price".

If you specify tier information, you must provide all the tiers you want to
create - the specified information will override the default. In addition, you
must supply a zero income tier. This is a requirement and the command will quit
if you don't have one set up, as that tier is used as the starting point for
financial assistance.

"""
import csv
from argparse import FileType
from datetime import date, datetime

import pytz
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.management import BaseCommand

from courses.models import Program
from ecommerce.constants import REDEMPTION_TYPE_UNLIMITED, PAYMENT_TYPE_FINANCIAL_ASSISTANCE
from ecommerce.models import Discount
from flexiblepricing.models import FlexiblePriceTier


class Command(BaseCommand):
    """
    Sets up tiers and discounts for a specified program (or DEDP, by default)
    """

    help = "Sets up tiers and discounts for a specified program (or DEDP, by default)"
    PROGRAM_READABLE_ID = "program-v1:MITx+DEDP"
    PROGRAM_TITLE = "Data, Economics and Development Policy"
    PROGRAM_ABBREV = "DEDP"

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--program",
            type=str,
            help=f"Program readable ID to use (default {self.PROGRAM_READABLE_ID})",
            nargs="?",
            default=self.PROGRAM_READABLE_ID,
        )

        parser.add_argument(
            "--program-name",
            type=str,
            help=f"Program name/title to use (default {self.PROGRAM_TITLE})",
            nargs="?",
            default=self.PROGRAM_TITLE,
        )

        parser.add_argument(
            "--program-abbrev",
            type=str,
            help=f"Program abbreviation (to use in discount code names, default {self.PROGRAM_ABBREV})",
            nargs="?",
            default=self.PROGRAM_ABBREV,
        )

        parser.add_argument(
            "--tier-info",
            type=FileType(mode="r"),
            help=f"Tiers to create (in CSV format: threshold,discount type,discount amount)",
        )

    def handle(self, *args, **kwargs):  # pylint: disable=unused-argument
        # Set defaults

        readable_id = (
            kwargs["program"] if "program" in kwargs else self.PROGRAM_READABLE_ID
        )
        program_title = (
            kwargs["program_name"] if "program_name" in kwargs else self.PROGRAM_TITLE
        )
        program_abbrev = (
            kwargs["program_abbrev"]
            if "program_abbrev" in kwargs
            else self.PROGRAM_ABBREV
        )

        current_year = date.today().year
        last_year = datetime(
            current_year - 1, 1, 1, tzinfo=pytz.timezone(settings.TIME_ZONE)
        )
        discounts_and_tiers = [
            {
                "tier": {"threshold": 0},
                "discount": {
                    "discount_code": f"{program_abbrev}-fa-tier1-{current_year}",
                    "discount_type": "dollars-off",
                    "amount": 750,
                },
            },
            {
                "tier": {"threshold": 25000},
                "discount": {
                    "discount_code": f"{program_abbrev}-fa-tier2-{current_year}",
                    "discount_type": "dollars-off",
                    "amount": 650,
                },
            },
            {
                "tier": {"threshold": 50000},
                "discount": {
                    "discount_code": f"{program_abbrev}-fa-tier3-{current_year}",
                    "discount_type": "dollars-off",
                    "amount": 500,
                },
            },
            {
                "tier": {"threshold": 75000},
                "discount": {
                    "discount_code": f"{program_abbrev}-fa-tier4-{current_year}",
                    "discount_type": "percent-off",
                    "amount": 0,
                },
            },
        ]
        content_type = ContentType.objects.filter(
            app_label="courses", model="program"
        ).first()

        # Step zero: if the user supplied a defaults file, then parse that

        if "tier_info" in kwargs and kwargs["tier_info"] is not None:
            discounts_and_tiers = []
            found_zero_tier = False

            self.stdout.write("Reading tier info from file...")

            with kwargs["tier_info"] as tierfile:
                csvreader = csv.DictReader(
                    tierfile, fieldnames=("threshold", "type", "value")
                )
                for (idx, row) in enumerate(csvreader):
                    self.stdout.write(
                        f"Read tier: threshold {row['threshold']}, discount type {row['type']}, value {row['value']}"
                    )
                    discounts_and_tiers.append(
                        {
                            "tier": {"threshold": row["threshold"]},
                            "discount": {
                                "discount_code": f"{program_abbrev}-fa-tier{idx+1}-{current_year}",
                                "discount_type": row["type"],
                                "amount": row["value"],
                            },
                        }
                    )

                    if int(row["threshold"]) == 0:
                        found_zero_tier = True

            self.stdout.write(f"Got {len(discounts_and_tiers)} tiers.")

            if not found_zero_tier:
                self.stdout.write(
                    self.style.ERROR(
                        "No zero tier specified in the tier info. This is a requirement - giving up."
                    )
                )
                return

        # Step one: get the DEDP program
        self.stdout.write(f"Setting up the program {program_title} ({readable_id})...")
        (program, created) = Program.objects.update_or_create(
            readable_id=readable_id,
            defaults={"title": program_title, "live": True},
        )
        if created:
            self.stdout.write(f"Created new program {program.id}")
        else:
            self.stdout.write(f"Using existing program {program.id}")

        # Step two: get existing discounts
        discounts = Discount.objects.filter(
            discount_code__startswith=f"{program_abbrev}-fa-tier",
            discount_code__endswith=str(current_year),
        ).all()
        self.stdout.write(f"{len(discounts)} existing {program_abbrev} discounts")

        matched_discounts = []

        # Step three: process any extant discounts
        # We need one each with the settings noted in the docs above
        for tier_config in discounts_and_tiers:
            self.stdout.write(
                f"Looking for {tier_config['discount']['amount']} {tier_config['discount']['discount_type']} discount for threshold {tier_config['tier']['threshold']}"
            )
            found_discount = None

            for discount in discounts:
                if (
                    discount.valid_now()
                    and tier_config["discount"]["discount_type"]
                    == discount.discount_type
                    and tier_config["discount"]["amount"] == discount.amount
                ):
                    found_discount = discount
                    self.stdout.write(f"\tFound a discount ({discount.discount_code})")
                    break

            if not found_discount:
                found_discount = Discount(
                    **tier_config["discount"],
                    payment_type=PAYMENT_TYPE_FINANCIAL_ASSISTANCE,
                    redemption_type=REDEMPTION_TYPE_UNLIMITED,
                )
                found_discount.save()
                self.stdout.write(f"\tCreated new discount ID {found_discount.id}")

            matched_discounts.append(found_discount)

            (tier, created) = FlexiblePriceTier.objects.update_or_create(
                income_threshold_usd=tier_config["tier"]["threshold"],
                courseware_object_id=program.id,
                courseware_content_type=content_type,
                defaults={"discount": found_discount, "current": True},
            )

            if created:
                self.stdout.write(
                    f"\tCreated new tier for threshold {tier_config['tier']['threshold']} - ID {tier.id}"
                )
            else:
                self.stdout.write(
                    f"\tUpdated existing tier ID {tier.id} for threshold {tier_config['tier']['threshold']}"
                )

        unmatched_discounts_qset = Discount.objects.filter(
            discount_code__startswith=f"{program_abbrev}-fa-tier"
        ).exclude(id__in=[discount.id for discount in matched_discounts])

        unmatched_discounts = unmatched_discounts_qset.update(expiration_date=last_year)

        self.stdout.write(f"{unmatched_discounts} discounts expired")

        unmatched_tiers = FlexiblePriceTier.objects.filter(
            courseware_object_id=program.id,
            courseware_content_type=content_type,
            discount__in=unmatched_discounts_qset.all(),
        ).update(current=False)

        self.stdout.write(f"{unmatched_tiers} tiers deactivated")
