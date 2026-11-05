"""Ecommerce email messages"""

from mail.messages import SiteTemplatedMessage


class OrderReceiptMessage(SiteTemplatedMessage):
    template_name = "mail/product_order_receipt"
    name = "Order Receipt"


class OrderRefundMessage(SiteTemplatedMessage):
    template_name = "mail/order_refund_message"
    name = "Refund of MITx Online Order"


class RefundRequestNotificationMessage(SiteTemplatedMessage):
    template_name = "mail/refund_request_notification"
    name = "Refund Request Submitted"
