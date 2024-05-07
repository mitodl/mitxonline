"""Ecommerce email messages"""

from mitol.mail.messages import TemplatedMessage


class OrderReceiptMessage(TemplatedMessage):
    template_name = "mail/product_order_receipt"
    name = "Order Receipt"


class OrderRefundMessage(TemplatedMessage):
    template_name = "mail/order_refund_message"
    name = "Refund of MITx Online Order"
