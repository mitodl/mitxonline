"""Constants for ecommerce."""

REFERENCE_NUMBER_PREFIX = "mitxonline-"

DISCOUNT_TYPE_PERCENT_OFF = "percent-off"
DISCOUNT_TYPE_DOLLARS_OFF = "dollars-off"
DISCOUNT_TYPE_FIXED_PRICE = "fixed-price"

ALL_DISCOUNT_TYPES = [
    DISCOUNT_TYPE_PERCENT_OFF,
    DISCOUNT_TYPE_DOLLARS_OFF,
    DISCOUNT_TYPE_FIXED_PRICE,
]
DISCOUNT_TYPES = list(zip(ALL_DISCOUNT_TYPES, ALL_DISCOUNT_TYPES))

REDEMPTION_TYPE_ONE_TIME = "one-time"
REDEMPTION_TYPE_ONE_TIME_PER_USER = "one-time-per-user"
REDEMPTION_TYPE_UNLIMITED = "unlimited"

ALL_REDEMPTION_TYPES = [
    REDEMPTION_TYPE_ONE_TIME,
    REDEMPTION_TYPE_ONE_TIME_PER_USER,
    REDEMPTION_TYPE_UNLIMITED,
]

REDEMPTION_TYPES = list(zip(ALL_REDEMPTION_TYPES, ALL_REDEMPTION_TYPES))

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
