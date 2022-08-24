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
