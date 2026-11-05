"""
Forcibly resolves a pending order.

An order may be sitting in the Pending state, even if the order is completed and
payment has been received. This command can be used to resolve those orders,
either by querying the payment processor for the status and acting appropriately,
or by forcing the order to the Fulfilled state.

The processor check finds a CyberSource order's transaction by searching for
its reference number. If the search can't find it, pass the transaction ID from
the CyberSource Business Center with --transaction-id to fetch it directly.
"""

from django.core.management import BaseCommand

from ecommerce.api import (
    check_and_process_pending_orders_for_resolution,
    fulfill_order_from_cybersource_transaction,
)
from ecommerce.models import PendingOrder


class Command(BaseCommand):
    """
    Resolve a pending order.
    """

    help = "Resolve a pending order."

    def add_arguments(self, parser) -> None:
        """Add arguments to the command."""

        parser.add_argument(
            "--order",
            type=str,
            help="The order reference number to look for (mitxonline-prod-1).",
            required=False,
        )

        parser.add_argument(
            "--all", action="store_true", help="Use all pending orders."
        )

        parser.add_argument(
            "--transaction-id",
            type=str,
            help="With --order, the CyberSource transaction ID to fulfill the order from, instead of searching CyberSource for it.",
            required=False,
        )

        parser.add_argument(
            "--no-check",
            action="store_true",
            help="Don't check with the payment processor, just mark the order as Fulfilled.",
        )

        parser.add_argument(
            "--no-fulfillment",
            action="store_true",
            help="Only mark the order as Fulfilled. Don't perform any fulfillment actions.",
        )

    def handle(self, *args, **kwargs):  # noqa: ARG002
        if not kwargs["all"] and not kwargs["order"]:
            self.stderr.write(self.style.ERROR("Please specify an order."))
            return

        if kwargs.get("transaction_id"):
            self._fulfill_from_transaction(**kwargs)
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
            pending_orders = []

        check = not kwargs.get("no_check", False)
        skip_fulfill = kwargs.get("no_fulfillment", False)

        (
            fulfilled_count,
            cancel_count,
            error_count,
        ) = check_and_process_pending_orders_for_resolution(
            pending_orders, check_status=check, skip_fulfillment=skip_fulfill
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Processed orders: {fulfilled_count} fulfilled, {cancel_count} canceled, {error_count} errored"
            )
        )

        if error_count > 0:
            self.stderr.write(self.style.ERROR(f"{error_count} orders had errors."))

    def _fulfill_from_transaction(self, **kwargs):
        """Fulfill the --order from the --transaction-id."""
        if kwargs["all"] or kwargs.get("no_check"):
            self.stderr.write(
                self.style.ERROR(
                    "--transaction-id needs a single --order and can't be used with --all or --no-check."
                )
            )
            return

        try:
            fulfill_order_from_cybersource_transaction(
                kwargs["order"],
                kwargs["transaction_id"],
                skip_fulfillment=kwargs.get("no_fulfillment", False),
            )
        except PendingOrder.DoesNotExist:
            self.stderr.write(
                self.style.ERROR(
                    f"Order {kwargs['order']} couldn't be found - is it a Pending CyberSource order?"
                )
            )
            return
        except ValueError as exc:
            self.stderr.write(self.style.ERROR(str(exc)))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Fulfilled order {kwargs['order']} from transaction {kwargs['transaction_id']}."
            )
        )
