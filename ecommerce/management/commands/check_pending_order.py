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
            help="The order ID to look for (mitxonline-prod-1).",
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
            ).all()

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
            pending_orders = PendingOrder.objects.filter(
                state=PendingOrder.STATE.PENDING
            ).all()

        refnos = [order.reference_number for order in pending_orders]

        if len(refnos) == 0:
            self.stdout.write(self.style.ERROR("No orders to consider."))
            return

        self.stdout.write(f"Looking up {len(refnos)} orders...")

        results = gateway.find_and_get_transactions(refnos)

        if len(results.keys()) == 0:
            self.stdout.write(
                self.style.ERROR("No pending orders found in CyberSource.")
            )
            return

        for result in results:
            payload = results[result]

            self.stdout.write(
                self.style.SUCCESS(
                    f"Found order {result} - state {payload['reason_code']}"
                )
            )

            if int(payload["reason_code"]) == 100:
                try:
                    order = PendingOrder.objects.filter(
                        state=PendingOrder.STATE.PENDING,
                        reference_number=payload["req_reference_number"],
                    ).get()

                    order.fulfill(payload)

                    self.stdout.write(
                        self.style.SUCCESS(f"Fulfilled order {order.reference_number}.")
                    )
                except Exception as e:
                    self.stderr.write(
                        self.style.ERROR(
                            f"Couldn't process pending order for fulfillment {payload['req_reference_number']}: {str(e)}"
                        )
                    )
            else:
                try:
                    order = PendingOrder.objects.filter(
                        state=PendingOrder.STATE.PENDING,
                        reference_number=payload["req_reference_number"],
                    ).get()

                    order.cancel()
                    order.transactions.create(
                        transaction_id=payload["transaction_id"],
                        amount=order.total_price_paid,
                        data=payload,
                        reason=f"Cancelled due to processor code {payload['reason_code']}",
                    )
                    order.save()

                    self.stdout.write(
                        self.style.SUCCESS(f"Cancelled order {order.reference_number}.")
                    )
                except Exception as e:
                    self.stderr.write(
                        self.style.ERROR(
                            f"Couldn't process pending order for cancellation {payload['req_reference_number']}: {str(e)}"
                        )
                    )
