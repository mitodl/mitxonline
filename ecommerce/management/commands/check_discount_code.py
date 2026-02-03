"""Check for and display info about a given discount code."""

from django.core.management import BaseCommand, CommandError
from rich import box
from rich.console import Console
from rich.table import Table

from ecommerce import constants
from ecommerce.models import Discount


class Command(BaseCommand):
    """Check for and display info about a given discount code."""

    def add_arguments(self, parser):
        """Add arguments to the command."""

        parser.add_argument(
            "code",
            type=str,
            help="The discount code to check.",
        )

    def handle(self, *args, **kwargs):  # noqa: C901, PLR0915, ARG002
        """Get and display code info."""

        code = kwargs.pop("code", None)

        if not code:
            msg = "Must have a code to check."
            raise CommandError(msg)

        code = Discount.objects.prefetch_related(
            "order_redemptions",
            "order_redemptions__redeemed_order",
            "order_redemptions__redeemed_by",
            "contract_redemptions",
            "contract_redemptions__contract",
            "contract_redemptions__user",
            "products",
            "user_discount_discount",
        ).get(discount_code=code)

        # Prefetch and format a bunch of things - mostly to keep debug mode
        # from messing up the output locally

        products = [
            (
                str(discount_product.product.id),
                str(discount_product.product.description),
            )
            for discount_product in code.products.all()
        ]
        assoc_users = [
            (str(user.username), str(user.email))
            for user in code.user_discount_discount.all()
        ]
        orders = [
            (
                str(order.redeemed_order.reference_number),
                str(order.redeemed_order.purchaser.email),
                str(order.redeemed_order.state),
                str(order.created_on),
            )
            for order in code.order_redemptions.all()
        ]
        attachments = [
            (
                str(attachment.user.email),
                str(attachment.contract.organization),
                str(attachment.contract),
                str(attachment.created_on),
            )
            for attachment in code.contract_redemptions.all()
        ]
        contracts = [
            (str(contract.organization), str(contract))
            for contract in code.b2b_contracts().all()
        ]

        bulk = "Yes" if code.is_bulk else "No"
        program = "Yes" if code.is_program_discount else "No"

        can_redeem = "No"

        if code.valid_now():
            if code.redemption_type == constants.REDEMPTION_TYPE_ONE_TIME_PER_USER:
                can_redeem = "Potentially"
            elif (
                code.redemption_type == constants.REDEMPTION_TYPE_UNLIMITED
                and code.max_redemptions
                and code.order_redemptions.count() < code.max_redemptions
            ) or (
                code.redemption_type == constants.REDEMPTION_TYPE_ONE_TIME
                and code.order_redemptions.count() == 0
            ):
                can_redeem = "Yes"

        self.stdout.write(f"Discount code {code.discount_code}")
        self.stdout.write(
            f"Kind: {code.friendly_format()} {code.discount_type} {code.redemption_type}"
        )
        self.stdout.write(f"Maximum redemptions: {code.max_redemptions}")
        self.stdout.write(f"Payment type: {code.payment_type}")
        self.stdout.write(f"Activation date: {code.activation_date}")
        self.stdout.write(f"Expiration date: {code.expiration_date}")
        self.stdout.write(f"Bulk discount? {bulk}")
        self.stdout.write(f"For program enrollments? {program}")
        self.stdout.write(f"Can be redeemed? {can_redeem}")
        self.stdout.write("\n")

        console = Console()

        if len(products) > 0:
            table = Table(title="Associated Products", box=box.MINIMAL)
            table.add_column("#", overflow="fold")
            table.add_column("Desc", overflow="fold")

            for product in products:
                table.add_row(*product)

            console.print(table)

        if len(assoc_users) > 0:
            table = Table(title="Associated Users", box=box.MINIMAL)
            table.add_column("Username", overflow="fold")
            table.add_column("Email", overflow="fold")

            for user in assoc_users:
                table.add_row(*user)

            console.print(table)

        if len(contracts) > 0:
            table = Table(title="Associated B2B Contracts", box=box.MINIMAL)
            table.add_column("Organization", overflow="fold")
            table.add_column("Contract", overflow="fold")

            for contract in contracts:
                table.add_row(*contract)

            console.print(table)

        if len(orders) > 0:
            table = Table(title="Order Redemptions", box=box.MINIMAL)
            table.add_column("Order ID", overflow="fold")
            table.add_column("User", overflow="fold")
            table.add_column("State")
            table.add_column("Created On")

            for order in orders:
                table.add_row(*order)

            console.print(table)

        if len(attachments) > 0:
            table = Table(title="Contract Attachment Redemptions", box=box.MINIMAL)
            table.add_column("User", overflow="fold")
            table.add_column("Organization")
            table.add_column("Contract", overflow="fold")
            table.add_column("Created On")

            for attachment in attachments:
                table.add_row(*attachment)

            console.print(table)
