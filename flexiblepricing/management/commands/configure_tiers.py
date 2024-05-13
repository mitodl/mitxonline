"""
Ensures there's a basic set of records present for financial assistance to work
for a program or course.

For a course, this includes:
- Ensuring the course is available

For a program, this includes:
- A program (required for the tiers to be set up)

For both, this includes:
- A set of discounts, specific to the program
- Tiers that are tied to these discounts

For more info on how this works, see the docs in
docs/source/commands/configure_tiers.rst.

"""

import csv
from argparse import FileType
from datetime import date, datetime

import pytz
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.management import BaseCommand, CommandError

from courses.models import Course, Program
from ecommerce.constants import (
    PAYMENT_TYPE_FINANCIAL_ASSISTANCE,
    REDEMPTION_TYPE_UNLIMITED,
)
from ecommerce.models import Discount
from flexiblepricing.models import FlexiblePriceTier


class Command(BaseCommand):
    """
    Sets up tiers and discounts for a specified program or course.
    """

    help = "Sets up tiers and discounts for a specified program or course."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--course", type=str, help="Course ID to use", nargs="?")
        parser.add_argument(
            "--program",
            type=str,
            help="Program readable ID to use.",
            nargs="?",
        )
        parser.add_argument(
            "--program-abbrev",
            type=str,
            help="Program abbreviation to use in discount code names.",
            nargs="?",
        )
        parser.add_argument(
            "--tier-info",
            type=FileType(mode="r"),
            help="Tiers to create in CSV format: threshold,discount type,discount amount",
        )

    def handle(self, *args, **kwargs):  # pylint: disable=unused-argument  # noqa: ARG002, C901, PLR0915
        # Ensure that either course or program is defined.
        if not any(x in kwargs for x in ["course", "program"]):
            self.stderr.write(
                self.style.ERROR(
                    "--course or --program must be specified as arguments when running the command."
                )
            )
            exit(-1)  # noqa: PLR1722

        try:
            course = (
                Course.objects.get(readable_id=kwargs["course"])
                if "course" in kwargs and kwargs["course"] is not None
                else None
            )
        except Exception as exc:  # noqa: BLE001
            raise CommandError(
                f"Couldn't find the course {kwargs['course']}, stopping."  # noqa: EM102
            ) from exc

        try:
            program = (
                Program.objects.get(readable_id=kwargs["program"])
                if "program" in kwargs and kwargs["program"] is not None
                else None
            )
        except Exception as exc:  # noqa: BLE001
            raise CommandError(
                f"Couldn't find the program {kwargs['program']}, stopping."  # noqa: EM102
            ) from exc

        discount_abbrev = (
            (program.readable_id if "program_abbrev" in kwargs else program.readable_id)
            if not course
            else course.readable_id
        )

        current_year = date.today().year  # noqa: DTZ011
        last_year = datetime(
            current_year - 1, 1, 1, tzinfo=pytz.timezone(settings.TIME_ZONE)
        )
        discounts_and_tiers = [
            {
                "tier": {"threshold": 0},
                "discount": {
                    "discount_code": f"{discount_abbrev}-fa-tier1-{current_year}",
                    "discount_type": "dollars-off" if not course else "percent-off",
                    "amount": 750 if not course else 75,
                },
            },
            {
                "tier": {"threshold": 25000},
                "discount": {
                    "discount_code": f"{discount_abbrev}-fa-tier2-{current_year}",
                    "discount_type": "dollars-off" if not course else "percent-off",
                    "amount": 650 if not course else 50,
                },
            },
            {
                "tier": {"threshold": 50000},
                "discount": {
                    "discount_code": f"{discount_abbrev}-fa-tier3-{current_year}",
                    "discount_type": "dollars-off" if not course else "percent-off",
                    "amount": 500 if not course else 25,
                },
            },
            {
                "tier": {"threshold": 75000},
                "discount": {
                    "discount_code": f"{discount_abbrev}-fa-tier4-{current_year}",
                    "discount_type": "percent-off",
                    "amount": 0,
                },
            },
        ]
        content_type = (
            ContentType.objects.filter(app_label="courses", model="program").first()
            if not course
            else ContentType.objects.filter(app_label="courses", model="course").first()
        )

        # Step zero: if the user supplied a defaults file, then parse that

        if "tier_info" in kwargs and kwargs["tier_info"] is not None:
            discounts_and_tiers = []
            found_zero_tier = False

            self.stdout.write("Reading tier info from file...")

            with kwargs["tier_info"] as tierfile:
                csvreader = csv.DictReader(
                    tierfile, fieldnames=("threshold", "type", "value")
                )
                for idx, row in enumerate(csvreader):
                    self.stdout.write(
                        f"Read tier: threshold {row['threshold']}, discount type {row['type']}, value {row['value']}"
                    )
                    discounts_and_tiers.append(
                        {
                            "tier": {"threshold": row["threshold"]},
                            "discount": {
                                "discount_code": f"{discount_abbrev}-fa-tier{idx+1}-{current_year}",
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

        # Step two: get existing discounts
        discounts = Discount.objects.filter(
            discount_code__startswith=f"{discount_abbrev}-fa-tier",
            discount_code__endswith=str(current_year),
        ).all()
        self.stdout.write(f"{len(discounts)} existing {discount_abbrev} discounts")

        matched_discounts = []

        # Step three: process any extant discounts
        # We need one each with the settings noted in the docs above
        courseware = course if course else program

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
                courseware_object_id=courseware.id,
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
            discount_code__startswith=f"{discount_abbrev}-fa-tier"
        ).exclude(id__in=[discount.id for discount in matched_discounts])

        unmatched_discounts = unmatched_discounts_qset.update(expiration_date=last_year)

        self.stdout.write(f"{unmatched_discounts} discounts expired")

        unmatched_tiers = FlexiblePriceTier.objects.filter(
            courseware_object_id=courseware.id,
            courseware_content_type=content_type,
            discount__in=unmatched_discounts_qset.all(),
        ).update(current=False)

        self.stdout.write(f"{unmatched_tiers} tiers deactivated")
