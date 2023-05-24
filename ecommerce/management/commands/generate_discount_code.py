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
amount is 100% or less. You can set the discount payment type using --payment-type.
The payment type should be one of (`marketing`, `sales`, `financial-assistance`,
`customer-support`, or `staff`).

"""

import csv

from django.core.management import BaseCommand

from ecommerce.api import generate_discount_code
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
            "--payment-type",
            type=str,
            help="Sets the payment type (marketing, sales, financial-assistance, customer-support, staff)",
            required=True,
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
        try:
            generated_codes = generate_discount_code(**kwargs)
        except Exception as e:
            self.stderr.write(self.style.ERROR(e))

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
