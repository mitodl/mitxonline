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


class VerifiedProgramNoEnrollmentError(Exception):
    """
    Raised if the learner is trying to get a verified enrollment in a program's
    course run but they don't have a verified enrollment in the program.
    """


class VerifiedProgramInvalidBasketError(Exception):
    """
    Raised if we've tried to process a verified enrollment for a program's course
    run, but the resulting basket wasn't zero-value (either because there's other
    things in the cart, or the discount is incorrect, or something like that).
    """


class VerifiedProgramInvalidOrderError(Exception):
    """
    Raised if we've tried to process a verified enrollment for a program's course
    run, but the processed order either had an error or it required payment.
    """
