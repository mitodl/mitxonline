"""Constants for ecommerce."""

from mitol.payment_gateway.api import ProcessorResponse
from mitol.payment_gateway.constants import (
    MITOL_PAYMENT_GATEWAY_CYBERSOURCE,
    MITOL_PAYMENT_GATEWAY_STRIPE,
)

REFERENCE_NUMBER_PREFIX = "mitxonline-"

# Standard self-service refund window, per the terms of service: learners may
# request a refund within this many days of purchase, or of the course start
# when they purchased before the course began.
REFUND_WINDOW_DAYS = 7

DISCOUNT_TYPE_PERCENT_OFF = "percent-off"
DISCOUNT_TYPE_DOLLARS_OFF = "dollars-off"
DISCOUNT_TYPE_FIXED_PRICE = "fixed-price"
DISCOUNT_TYPE_PAID_AMOUNT_OFF = "paid-amount-off"

ALL_DISCOUNT_TYPES = [
    DISCOUNT_TYPE_PERCENT_OFF,
    DISCOUNT_TYPE_DOLLARS_OFF,
    DISCOUNT_TYPE_FIXED_PRICE,
    DISCOUNT_TYPE_PAID_AMOUNT_OFF,
]
DISCOUNT_TYPES = list(zip(ALL_DISCOUNT_TYPES, ALL_DISCOUNT_TYPES))

# paid-amount-off implies the program-child-purchase redemption type and a
# stored amount of 0, so the randomized test factories and bulk code
# generation draw from this subset instead.
STANDARD_DISCOUNT_TYPES = [
    discount_type
    for discount_type in ALL_DISCOUNT_TYPES
    if discount_type != DISCOUNT_TYPE_PAID_AMOUNT_OFF
]

REDEMPTION_TYPE_ONE_TIME = "one-time"
REDEMPTION_TYPE_ONE_TIME_PER_USER = "one-time-per-user"
REDEMPTION_TYPE_UNLIMITED = "unlimited"
REDEMPTION_TYPE_PROGRAM_CHILD_PURCHASE = "program-child-purchase"

ALL_REDEMPTION_TYPES = [
    REDEMPTION_TYPE_ONE_TIME,
    REDEMPTION_TYPE_ONE_TIME_PER_USER,
    REDEMPTION_TYPE_UNLIMITED,
    REDEMPTION_TYPE_PROGRAM_CHILD_PURCHASE,
]

REDEMPTION_TYPES = list(zip(ALL_REDEMPTION_TYPES, ALL_REDEMPTION_TYPES))

# program-child-purchase forces automatic=True and program-only product
# links even when paired with a standard calculation, so the random draw
# skips it too.
STANDARD_REDEMPTION_TYPES = [
    redemption_type
    for redemption_type in ALL_REDEMPTION_TYPES
    if redemption_type != REDEMPTION_TYPE_PROGRAM_CHILD_PURCHASE
]

PAYMENT_TYPE_MARKETING = "marketing"
PAYMENT_TYPE_SALES = "sales"
PAYMENT_TYPE_FINANCIAL_ASSISTANCE = "financial-assistance"
PAYMENT_TYPE_CUSTOMER_SUPPORT = "customer-support"
PAYMENT_TYPE_STAFF = "staff"
PAYMENT_TYPE_LEGACY = "legacy"

ALL_PAYMENT_TYPES = [
    PAYMENT_TYPE_MARKETING,
    PAYMENT_TYPE_SALES,
    PAYMENT_TYPE_FINANCIAL_ASSISTANCE,
    PAYMENT_TYPE_CUSTOMER_SUPPORT,
    PAYMENT_TYPE_STAFF,
    PAYMENT_TYPE_LEGACY,
]

PAYMENT_TYPES = list(zip(ALL_PAYMENT_TYPES, ALL_PAYMENT_TYPES))

TRANSACTION_TYPE_REFUND = "refund"
TRANSACTION_TYPE_PAYMENT = "payment"

ALL_TRANSACTION_TYPES = [TRANSACTION_TYPE_PAYMENT, TRANSACTION_TYPE_REFUND]

TRANSACTION_TYPES = list(zip(ALL_TRANSACTION_TYPES, ALL_TRANSACTION_TYPES))

CYBERSOURCE_CARD_TYPES = {
    "001": "Visa",
    "002": "Mastercard",
    "003": "American Express",
    "004": "Discover",
    "005": "Diners Club",
    "006": "Carte Blanche",
    "007": "JCB",
    "014": "Enroute",
    "021": "JAL",
    "024": "Maestro (UK)",
    "031": "Delta",
    "033": "Visa Electron",
    "034": "Dankort",
    "036": "Carte Bancaires",
    "037": "Carta Si",
    "039": "EAN",
    "040": "UATP",
    "042": "Maestro (Intl)",
    "050": "Hipercard",
    "051": "Aura",
    "054": "Elo",
    "061": "RuPay",
    "062": "China UnionPay",
}

REFUND_SUCCESS_STATES = [
    ProcessorResponse.STATE_ACCEPTED,
    ProcessorResponse.STATE_PENDING,
]

ZERO_PAYMENT_DATA = {
    "amount": 0,
    "transaction_id": "zero-payment-transaction",
    "data": {"reason": "No payment required"},
    "is_administrative": True,
}
ADMIN_FULFILLED_PAYMENT_DATA = {
    "amount": 0,
    "transaction_id": "administratively-fulfilled",
    "data": {"reason": "Order fulfilled administratively."},
    "is_administrative": True,
}

PAYMENT_HOOK_ACTION_PRE_SALE = "presale"
PAYMENT_HOOK_ACTION_POST_SALE = "postsale"
PAYMENT_HOOK_ACTION_POST_REFUND = "postrefund"
PAYMENT_HOOK_ACTION_TEST = "test"

PAYMENT_HOOK_ACTIONS = [
    PAYMENT_HOOK_ACTION_PRE_SALE,
    PAYMENT_HOOK_ACTION_POST_SALE,
    PAYMENT_HOOK_ACTION_POST_REFUND,
    PAYMENT_HOOK_ACTION_TEST,
]

GEOLOCATION_TYPE_PROFILE = "profile"
GEOLOCATION_TYPE_GEOIP = "geoip"
GEOLOCATION_TYPE_NONE = "none"
GEOLOCATION_TYPES = [
    GEOLOCATION_TYPE_PROFILE,
    GEOLOCATION_TYPE_GEOIP,
    GEOLOCATION_TYPE_NONE,
]
GEOLOCATION_CHOICES = zip(GEOLOCATION_TYPES, GEOLOCATION_TYPES)

CHECKOUT_SUCCESS_ROUTE_MAP = {
    "None": "checkout-result-callback",
    MITOL_PAYMENT_GATEWAY_CYBERSOURCE: "checkout-result-callback",
    MITOL_PAYMENT_GATEWAY_STRIPE: "checkout-result-callback",
}
CHECKOUT_CANCEL_ROUTE_MAP = {
    "None": "checkout-result-callback",
    MITOL_PAYMENT_GATEWAY_CYBERSOURCE: "checkout-result-callback",
    MITOL_PAYMENT_GATEWAY_STRIPE: "checkout-result-callback",
}

STRIPE_TRANSACTION_REASON_INITIAL_CHECKOUTSESSION = "Initial CheckoutSession"

STRIPE_OBJECT_CHECKOUT_SESSION = "checkout.session"

STRIPE_EVENT_CHECKOUT_SESSION_COMPLETED = "checkout.session.completed"
STRIPE_EVENT_CHECKOUT_SESSION_EXPIRED = "checkout.session.expired"
STRIPE_EVENT_CHECKOUT_SESSION_ASYNC_PAYMENT_FAILED = (
    "checkout.session.async_payment_failed"
)
STRIPE_EVENT_CHECKOUT_SESSION_ASYNC_PAYMENT_SUCCEEDED = (
    "checkout.session.async_payment_succeeded"
)

STRIPE_EVENTS_CHECKOUT_SESSION = [
    STRIPE_EVENT_CHECKOUT_SESSION_COMPLETED,
    STRIPE_EVENT_CHECKOUT_SESSION_EXPIRED,
    STRIPE_EVENT_CHECKOUT_SESSION_ASYNC_PAYMENT_FAILED,
    STRIPE_EVENT_CHECKOUT_SESSION_ASYNC_PAYMENT_SUCCEEDED,
]

STRIPE_PAYMENT_STATUS_PAID = "paid"
STRIPE_PAYMENT_STATUS_NPR = "no_payment_required"
STRIPE_PAYMENT_STATUS_UNPAID = "unpaid"

STRIPE_PAYMENT_STATUSES_GOOD = [STRIPE_PAYMENT_STATUS_NPR, STRIPE_PAYMENT_STATUS_PAID]

STRIPE_CHECKOUT_SESSION_STATUS_COMPLETE = "complete"
STRIPE_CHECKOUT_SESSION_STATUS_EXPIRED = "expired"
STRIPE_CHECKOUT_SESSION_STATUS_OPEN = "open"

STRIPE_PAYMENT_INTENT_STATUS_PROCESSING = "processing"
STRIPE_PAYMENT_INTENT_STATUS_SUCCEEDED = "succeeded"
STRIPE_PAYMENT_INTENT_STATUS_CANCELLED = "cancelled"
STRIPE_PAYMENT_INTENT_STATUS_REQUIRES_ACTION = "requires_action"
STRIPE_PAYMENT_INTENT_STATUS_REQUIRES_CAPTURE = "requires_capture"
STRIPE_PAYMENT_INTENT_STATUS_REQUIRES_CONFIRMATION = "requires_confirmation"
STRIPE_PAYMENT_INTENT_STATUS_REQUIRES_PAYMENT_METHOD = "requires_payment_method"

STRIPE_PAYMENT_INTENT_STATUSES_COMPLETE = [
    STRIPE_PAYMENT_INTENT_STATUS_SUCCEEDED,
    STRIPE_PAYMENT_INTENT_STATUS_CANCELLED,
    STRIPE_PAYMENT_INTENT_STATUS_REQUIRES_ACTION,
    STRIPE_PAYMENT_INTENT_STATUS_REQUIRES_CAPTURE,
    STRIPE_PAYMENT_INTENT_STATUS_REQUIRES_CONFIRMATION,
    STRIPE_PAYMENT_INTENT_STATUS_REQUIRES_PAYMENT_METHOD,
]

STRIPE_OVERALL_CHECKOUT_STATUS_PENDING = "pending"
STRIPE_OVERALL_CHECKOUT_STATUS_PENDING_ACTION = "pending-action"
STRIPE_OVERALL_CHECKOUT_STATUS_PAID = "paid"
STRIPE_OVERALL_CHECKOUT_STATUS_CANCELLED = "cancelled"
STRIPE_OVERALL_CHECKOUT_STATUS_ERROR = "error"
