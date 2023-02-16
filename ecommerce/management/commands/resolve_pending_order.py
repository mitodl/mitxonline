"""
Looks up pending orders in CyberSource, and changes the status of the order if
necessary.

Occasionally, there may be a breakdown of communication between MITx Online and
CyberSource, and orders that have gone through on the CyberSource end may not
have their updated status reflected in MITx Online. This command will find those
orders (or, alternatively, look at the specified order) and then will either
fulfill or cancel the order as necessary.

"""

from django.core.exceptions import ObjectDoesNotExist
from django.core.management import BaseCommand
from mitol.payment_gateway.api import PaymentGateway

from ecommerce.api import check_and_process_pending_orders_for_resolution
from ecommerce.models import PendingOrder
from main.settings import ECOMMERCE_DEFAULT_PAYMENT_GATEWAY


class Command(BaseCommand):
    """
    Looks up pending orders in CyberSource, and changes the status of the order if necessary.
    """

    help = "Looks up pending orders in CyberSource, and changes the status of the order if necessary."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--order",
            type=str,
            help="The order reference number to look for (mitxonline-prod-1).",
            required=False,
        )

        parser.add_argument(
            "--all", action="store_true", help="Use all pending orders."
        )

    def handle(self, *args, **kwargs):
        gateway = PaymentGateway.get_gateway_class(ECOMMERCE_DEFAULT_PAYMENT_GATEWAY)

        if not kwargs["all"] and not kwargs["order"]:
            self.stderr.write(self.style.ERROR("Please specify an order."))
            return

        if not kwargs["all"]:
            pending_orders = PendingOrder.objects.filter(
                reference_number=kwargs["order"]
            ).values_list("reference_number")

            if len(pending_orders) == 0:
                self.stderr.write(
                    self.style.ERROR(
                        f"Order {kwargs['order']} couldn't be found - is it Pending?"
                    )
                )
                return
            elif len(pending_orders) > 1:
                self.stderr.write(
                    self.style.ERROR(
                        f"Order {kwargs['order']} returned multiple matches ({len(pending_orders)})"
                    )
                )
                return
        else:
            pending_orders = None

        (
            fulfilled_count,
            cancel_count,
            error_count,
        ) = check_and_process_pending_orders_for_resolution(pending_orders)

        self.stdout.write(
            self.style.SUCCESS(
                f"Processed orders: {fulfilled_count} fulfilled, {cancel_count} canceled, {error_count} errored"
            )
        )

        if error_count > 0:
            self.stderr.write(self.style.ERROR(f"{error_count} orders had errors."))
