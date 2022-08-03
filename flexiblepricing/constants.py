from urllib.parse import quote_plus

from django.conf import settings


class FlexiblePriceStatus:
    """Statuses for the FlexiblePrice model"""

    APPROVED = "approved"
    AUTO_APPROVED = "auto-approved"
    CREATED = "created"
    PENDING_MANUAL_APPROVAL = "pending-manual-approval"
    DENIED = "denied"
    RESET = "reset"

    ALL_STATUSES = [
        APPROVED,
        AUTO_APPROVED,
        CREATED,
        PENDING_MANUAL_APPROVAL,
        DENIED,
        RESET,
    ]
    TERMINAL_STATUSES = [APPROVED, AUTO_APPROVED, DENIED]

    STATUS_MESSAGES_DICT = {
        APPROVED: "Approved",
        AUTO_APPROVED: "Auto-Approved",
        CREATED: "--",
        PENDING_MANUAL_APPROVAL: "Pending Approval (Documents Received)",
        DENIED: "Denied",
    }


COUNTRY = "country"
DEFAULT_INCOME_THRESHOLD = 75000
INCOME = "income"
INCOME_THRESHOLD_FIELDS = [COUNTRY, INCOME]

FLEXIBLE_PRICE_EMAIL_RESET_SUBJECT = (
    "Update to your personalized course price for {program_name} MITxOnline"
)
FLEXIBLE_PRICE_EMAIL_RESET_MESSAGE = (
    "As requested, we have reset your personalized course price. Please visit "
    "the MITxOnline dashboard and re-submit your annual income information."
)

FLEXIBLE_PRICE_EMAIL_APPROVAL_SUBJECT = (
    "Your personalized course price for {program_name} MITxOnline"
)
FLEXIBLE_PRICE_EMAIL_APPROVAL_MESSAGE = (
    "After reviewing your income documentation, the {program_name} MITxOnline team has determined "
    "that your personalized course price is ${price}.\n\n"
    "You can pay for MITxOnline courses through the MITxOnline portal "
    "(https://MITxOnline.mit.edu/dashboard). All coursework will be conducted on mitxonline.mit.edu"
)

FLEXIBLE_PRICE_EMAIL_DOCUMENTS_RECEIVED_SUBJECT = (
    "Documents received for {program_name} MITxOnline"
)
FLEXIBLE_PRICE_EMAIL_DOCUMENTS_RECEIVED_MESSAGE = (
    "We have received your documents verifying your income. We will review and process them within "
    "5 working days. If you have not received a confirmation email within one week, please feel free "
    "to reply to this email. Otherwise you should receive a confirmation email with your course price. "
    "\n\n"
    "While you are waiting, we encourage you to enroll now and pay later, when a decision has been "
    "reached."
)


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
