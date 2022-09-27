"""Ecommerce mail functions"""
import pycountry
import logging

from decimal import Decimal
from dateutil import parser
from mitol.mail.api import get_message_sender

from ecommerce.messages import OrderReceiptMessage, OrderRefundMessage
from ecommerce.constants import TRANSACTION_TYPE_REFUND

log = logging.getLogger()


def send_ecommerce_order_receipt(order_record):
    """
    Send emails receipt summarizing the user purchase detail.

    Args:
        order_record: An order.
    """
    from ecommerce.serializers import OrderReceiptSerializer

    data = OrderReceiptSerializer(instance=order_record).data
    purchaser = data.get("purchaser")
    coupon = data.get("coupon")
    lines = data.get("lines")
    order = data.get("order")
    receipt = data.get("receipt")
    country = pycountry.countries.get(alpha_2=purchaser.get("country"))
    recipient = purchaser.get("email")

    try:
        with get_message_sender(OrderReceiptMessage) as sender:
            sender.build_and_send_message(
                recipient,
                {
                    "coupon": coupon,
                    "content_title": lines[0].get("content_title") if lines else None,
                    "lines": lines,
                    "order_total": format(
                        sum(float(line["total_paid"]) for line in lines),
                        ".2f",
                    ),
                    "order": {
                        "reference_number": order.get("reference_number"),
                        "created_on": parser.parse(order.get("created_on")),
                        "id": order.get("id"),
                    },
                    "receipt": receipt,
                    "purchaser": {
                        "name": " ".join(
                            [
                                purchaser.get("first_name"),
                                purchaser.get("last_name"),
                            ]
                        ),
                        "email": purchaser.get("email"),
                        "street_address": purchaser.get("street_address"),
                        "state_code": purchaser.get("state_or_territory").split("-")[
                            -1
                        ],
                        "postal_code": purchaser.get("postal_code"),
                        "city": purchaser.get("city"),
                        "country": country.name if country else None,
                        "company": purchaser.get("company"),
                    },
                },
            )

    except:  # pylint: disable=bare-except
        log.exception("Error sending order receipt email.")


def send_ecommerce_refund_message(order_record):
    recipient = order_record.purchaser.email
    line = order_record.lines.first()
    transaction = (
        order_record.transactions.filter(transaction_type=TRANSACTION_TYPE_REFUND)
        .order_by("-created_on")
        .first()
    )

    try:
        with get_message_sender(OrderRefundMessage) as sender:
            sender.build_and_send_message(
                recipient,
                {
                    "order": order_record,
                    "readable_id": line.purchased_object.readable_id.split('+')[1] if line else None,
                    "title": line.purchased_object.title if line else None,
                    "transaction_amount": transaction.amount.quantize(Decimal("0.01")),
                },
            )
    except:
        log.exception("Error sending order refund email.")
