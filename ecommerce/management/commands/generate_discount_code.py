"""
Generates discount (sometimes called enrollment) codes with some parameters. 
This is meant to be an easy way to make these in bulk - for one-offs, you can 
use this or go through Django Admin (or, eventually, the Staff Dashboard). 

Codes can be created in one of two ways: you can specify the codes themselves on
the command line, or you can specify --count and --prefix and have it generate
the codes. 
    * Codes (literally, the code that the learner will enter) are just listed
      on the command line. Any number of these can be specified, but you must 
      provide at least one if you're explicitly specifying the code. All codes 
      will share the same options (type, amount, expiration date, etc.)
    * If you use --count and --prefix, the command will generate the specified
      amount of codes using the given prefix and a UUID. Discount code length is
      limited to 50 so your prefix must be 13 characters or less. Include any
      punctuation that you need in the prefix - the command will not, for
      example, add a dash between the prefix and the UUID. 

The default is to generate a dollars off discount code in the specified amount,
without an expiration date, and with unlimited redemptions. Use the --expires
option to specify an expiration date, or use --one-time to make the code a
one-time discount. You can also set the discount type with --discount-type. The
type should be one of the normal types (dollars-off, percent-off, or 
fixed-price). If the type is set to percent-off, the command will make sure your
amount is 100% or less. 

"""

import csv
import uuid
from decimal import Decimal

from django.core.management import BaseCommand

from ecommerce.constants import (
    ALL_DISCOUNT_TYPES,
    DISCOUNT_TYPE_PERCENT_OFF,
    REDEMPTION_TYPE_ONE_TIME,
    REDEMPTION_TYPE_ONE_TIME_PER_USER,
    REDEMPTION_TYPE_UNLIMITED,
)
from ecommerce.models import Discount
from main.utils import parse_supplied_date


class Command(BaseCommand):
    """
    Generates discount (sometimes called enrollment) codes with some parameters.
    """

    help = "Generates discount/enrollment codes."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--prefix",
            type=str,
            help="The prefix to use for the codes. (Maximum length 13 characters)",
        )

        parser.add_argument(
            "--expires",
            type=str,
            help="Optional expiration date for the code, in ISO-8601 (YYYY-MM-DD) format.",
        )

        parser.add_argument(
            "--activates",
            type=str,
            help="Optional activation date for the code, in ISO-8601 (YYYY-MM-DD) format.",
        )

        parser.add_argument(
            "--discount-type",
            type=str,
            help="Sets the discount type (dollars-off, percent-off, fixed-price; default percent-off)",
            default="percent-off",
        )

        parser.add_argument(
            "--amount",
            type=str,
            nargs="?",
            help="Sets the discount amount",
            required=True,
        )

        parser.add_argument(
            "--count",
            type=int,
            nargs="?",
            help="Number of codes to produce",
            default=1,
        )

        parser.add_argument(
            "--one-time",
            help="Make the resulting code(s) one-time redemptions (otherwise, default to unlimited)",
            action="store_true",
        )

        parser.add_argument(
            "--once-per-user",
            help="Make the resulting code(s) one-time per user redemptions (otherwise, default to unlimited)",
            action="store_true",
        )

        parser.add_argument(
            "codes",
            nargs="*",
            type=str,
            help="Discount codes to generate (ignored if --count is specified)",
        )

    def handle(self, *args, **kwargs):  # pylint: disable=unused-argument
        codes_to_generate = []
        discount_type = kwargs["discount_type"]
        redemption_type = REDEMPTION_TYPE_UNLIMITED
        amount = Decimal(kwargs["amount"])

        if kwargs["discount_type"] not in ALL_DISCOUNT_TYPES:
            self.stderr.write(
                self.style.ERROR(
                    f"Discount type {kwargs['discount_type']} is not valid."
                )
            )
            exit(-1)

        if kwargs["discount_type"] == DISCOUNT_TYPE_PERCENT_OFF and amount > 100:
            self.stderr.write(
                self.style.ERROR(
                    f"Discount amount {amount} not valid for discount type {DISCOUNT_TYPE_PERCENT_OFF}."
                )
            )
            exit(-1)

        if kwargs["count"] > 1 and "prefix" not in kwargs:
            self.stderr.write(
                self.style.ERROR(
                    "You must specify a prefix to create a batch of codes."
                )
            )
            exit(-1)

        if kwargs["count"] > 1:
            prefix = kwargs["prefix"]

            if len(prefix) > 13:
                self.stderr.write(
                    self.style.ERROR(
                        f"Prefix {prefix} is {len(prefix)} - prefixes must be 13 characters or less."
                    )
                )
                exit(-1)

            for i in range(0, kwargs["count"]):
                generated_uuid = uuid.uuid4()
                code = f"{prefix}{generated_uuid}"

                codes_to_generate.append(code)
        else:
            codes_to_generate = kwargs["codes"]

        if "one_time" in kwargs and kwargs["one_time"]:
            redemption_type = REDEMPTION_TYPE_ONE_TIME

        if "once_per_user" in kwargs and kwargs["once_per_user"]:
            redemption_type = REDEMPTION_TYPE_ONE_TIME_PER_USER

        if "expires" in kwargs and kwargs["expires"] is not None:
            expiration_date = parse_supplied_date(kwargs["expires"])
        else:
            expiration_date = None

        if "activates" in kwargs and kwargs["activates"] is not None:
            activation_date = parse_supplied_date(kwargs["activates"])
        else:
            activation_date = None

        generated_codes = []

        for code_to_generate in codes_to_generate:
            try:
                discount = Discount.objects.create(
                    discount_type=discount_type,
                    redemption_type=redemption_type,
                    expiration_date=expiration_date,
                    activation_date=activation_date,
                    discount_code=code_to_generate,
                    amount=amount,
                    for_flexible_pricing=False,
                )

                generated_codes.append(discount)
            except:
                self.stderr.write(
                    self.style.ERROR(
                        f"Discount code {code_to_generate} could not be created - maybe it already exists?"
                    )
                )

        with open("generated-codes.csv", mode="w") as output_file:
            writer = csv.DictWriter(
                output_file, ["code", "type", "amount", "expiration_date"]
            )

            writer.writeheader()

            for code in generated_codes:
                writer.writerow(
                    {
                        "code": code.discount_code,
                        "type": code.discount_type,
                        "amount": code.amount,
                        "expiration_date": code.expiration_date,
                    }
                )

        self.stdout.write(self.style.SUCCESS(f"{len(generated_codes)} created."))
