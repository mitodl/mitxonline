from urllib.parse import quote_plus

from django.conf import settings


class FlexiblePriceStatus:
    """Statuses for the FlexiblePrice model"""

    APPROVED = "approved"
    AUTO_APPROVED = "auto-approved"
    CREATED = "created"
    PENDING_MANUAL_APPROVAL = "pending-manual-approval"
    SKIPPED = "skipped"
    RESET = "reset"

    ALL_STATUSES = [
        APPROVED,
        AUTO_APPROVED,
        CREATED,
        PENDING_MANUAL_APPROVAL,
        SKIPPED,
        RESET,
    ]
    TERMINAL_STATUSES = [APPROVED, AUTO_APPROVED, SKIPPED]

    STATUS_MESSAGES_DICT = {
        APPROVED: "Approved",
        AUTO_APPROVED: "Auto-Approved",
        CREATED: "--",
        PENDING_MANUAL_APPROVAL: "Pending Approval (Documents Received)",
        SKIPPED: "Skipped",
    }


COUNTRY = "country"
INCOME = "income"
INCOME_THRESHOLD_FIELDS = [COUNTRY, INCOME]


def get_currency_exchange_rate_api_request_url():
    """
    Helper function to build the CURRENCY_EXCHANGE_RATE_API_REQUEST_URL
    """
    if settings.OPEN_EXCHANGE_RATES_URL and settings.OPEN_EXCHANGE_RATES_APP_ID:
        return "{url}latest.json?app_id={app_id}".format(
            url=settings.OPEN_EXCHANGE_RATES_URL,
            app_id=quote_plus(settings.OPEN_EXCHANGE_RATES_APP_ID),
        )
    else:
        return None  # pragma: no cover
