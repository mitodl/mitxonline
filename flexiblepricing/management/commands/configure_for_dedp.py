"""
Ensures there's a basic set of records present for financial aid to work for
DEDP courses. This includes:
- A DEDP program (required for the tiers to be set up)
- A set of discounts, specific to DEDP
- Tiers that are tied to these discounts

The defaults for this are:

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

"""
from datetime import date, datetime
from django.core.management import BaseCommand
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
import pytz

from courses.models import Program
from flexiblepricing.models import FlexiblePriceTier
from ecommerce.models import Discount
from ecommerce.constants import REDEMPTION_TYPE_UNLIMITED


class Command(BaseCommand):
    """
    Sets up some basic records for DEDP Financial Assistance
    """

    help = "Sets up some basic records for DEDP Financial Assistance"
    PROGRAM_READABLE_ID = "program-v1:MITx+DEDP"

    def handle(self, *args, **kwargs):  # pylint: disable=unused-argument
        current_year = date.today().year
        last_year = datetime(
            current_year - 1, 1, 1, tzinfo=pytz.timezone(settings.TIME_ZONE)
        )
        discounts_and_tiers = [
            {
                "tier": {"threshold": 0},
                "discount": {
                    "discount_code": f"DEDP-fa-tier1-{current_year}",
                    "discount_type": "dollars-off",
                    "amount": 750,
                },
            },
            {
                "tier": {"threshold": 25000},
                "discount": {
                    "discount_code": f"DEDP-fa-tier2-{current_year}",
                    "discount_type": "dollars-off",
                    "amount": 650,
                },
            },
            {
                "tier": {"threshold": 50000},
                "discount": {
                    "discount_code": f"DEDP-fa-tier3-{current_year}",
                    "discount_type": "dollars-off",
                    "amount": 500,
                },
            },
            {
                "tier": {"threshold": 75000},
                "discount": {
                    "discount_code": f"DEDP-fa-tier4-{current_year}",
                    "discount_type": "percent-off",
                    "amount": 0,
                },
            },
        ]
        content_type = ContentType.objects.filter(
            app_label="courses", model="program"
        ).first()

        # Step one: get the DEDP program
        self.stdout.write(self.style.NOTICE("Setting up the program..."))
        (program, created) = Program.objects.update_or_create(
            readable_id=self.PROGRAM_READABLE_ID,
            defaults={"title": "Data, Economics and Development Policy", "live": True},
        )
        if created:
            self.stdout.write(self.style.NOTICE(f"Created new program {program.id}"))
        else:
            self.stdout.write(self.style.NOTICE(f"Using existing program {program.id}"))

        # Step two: get existing discounts
        discounts = Discount.objects.filter(
            discount_code__startswith="DEDP-fa-tier",
            discount_code__endswith=str(current_year),
        ).all()
        self.stdout.write(
            self.style.NOTICE(f"{len(discounts)} existing DEDP discounts")
        )

        matched_discounts = []

        # Step three: process any extant discounts
        # We need one each with the settings noted in the docs above
        for tier_config in discounts_and_tiers:
            self.stdout.write(
                self.style.NOTICE(
                    f"Looking for {tier_config['discount']['amount']} {tier_config['discount']['discount_type']} discount for threshold {tier_config['tier']['threshold']}"
                )
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
                    self.stdout.write(
                        self.style.NOTICE(
                            f"\tFound a discount ({discount.discount_code})"
                        )
                    )
                    break

            if not found_discount:
                found_discount = Discount(
                    **tier_config["discount"],
                    for_flexible_pricing=True,
                    redemption_type=REDEMPTION_TYPE_UNLIMITED,
                )
                found_discount.save()
                self.stdout.write(
                    self.style.NOTICE(f"\tCreated new discount ID {found_discount.id}")
                )

            matched_discounts.append(found_discount)

            (tier, created) = FlexiblePriceTier.objects.update_or_create(
                income_threshold_usd=tier_config["tier"]["threshold"],
                courseware_object_id=program.id,
                courseware_content_type=content_type,
                defaults={"discount": found_discount, "current": True},
            )

            if created:
                self.stdout.write(
                    self.style.NOTICE(
                        f"\tCreated new tier for threshold {tier_config['tier']['threshold']} - ID {tier.id}"
                    )
                )
            else:
                self.stdout.write(
                    self.style.NOTICE(
                        f"\tUpdated existing tier ID {tier.id} for threshold {tier_config['tier']['threshold']}"
                    )
                )

        unmatched_discounts_qset = Discount.objects.filter(
            discount_code__startswith="DEDP-fa-tier"
        ).exclude(id__in=[discount.id for discount in matched_discounts])

        unmatched_discounts = unmatched_discounts_qset.update(expiration_date=last_year)

        self.stdout.write(self.style.NOTICE(f"{unmatched_discounts} discounts expired"))

        unmatched_tiers = FlexiblePriceTier.objects.filter(
            courseware_object_id=program.id,
            courseware_content_type=content_type,
            discount__in=unmatched_discounts_qset.all(),
        ).update(current=False)

        self.stdout.write(self.style.NOTICE(f"{unmatched_tiers} tiers deactivated"))
