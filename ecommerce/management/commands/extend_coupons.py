
from django.core.management import BaseCommand

from ecommerce.models import Discount
from main.utils import parse_supplied_date


class Command(BaseCommand):
    """
    Extends existing unused discount codes with some parameters.

    Make sure that the prefix you are providing has a term associated with the discount or that
    it is unique across all discounts.

    ./manage.py extend_coupons --discount-code-prefix B2B_NNN_2T2025_ --expires 2026-12-12
    """

    help = "Extend expiration date for unused coupons discount/enrollment codes."

    def add_arguments(self, parser) -> None:

        parser.add_argument(
            "--expires",
            type=str,
            help="Expiration date for the code, in ISO-8601 (YYYY-MM-DD) format.",
            required=True,
        )

        parser.add_argument(
            "--discount-code-prefix",
            type=str,
            help="The prefix to filter the codes for extension.",
            required=True,
        )

    def handle(self, *args, **kwargs):  # pylint: disable=unused-argument  # noqa: ARG002
        """
        Extends the expiration date of discount codes that match a given prefix.
        """

        code_prefix = kwargs.get("discount_code_prefix")
        discounts = Discount.objects.filter(discount_code__contains=code_prefix)
        extension_date = parse_supplied_date(kwargs.get("expires"))

        for discount_code in discounts:
            if not discount_code.is_redeemed:
                discount_code.expiration_date = extension_date
                discount_code.save()

        self.stdout.write(self.style.SUCCESS(f"Coupons expiration date extended."))
