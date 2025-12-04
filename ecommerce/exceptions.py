"""Exceptions for payments app."""


class ProductBlockedError(Exception):
    """
    Raised if the user attempts to add a product, but they're blocked for
    whatever reason.
    """


class PaypalRefundError(Exception):
    """Raised when attempting to refund an order that was paid via PayPal."""


class PaymentGatewayError(Exception):
    """
    Raised when the payment gateway gives us an error, but didn't raise its own
    exception.
    """
