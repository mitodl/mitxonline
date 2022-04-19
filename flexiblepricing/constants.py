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
