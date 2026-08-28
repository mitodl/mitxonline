"""Constants for the B2B app."""

ORG_INDEX_SLUG = "organizations"

CONTRACT_MEMBERSHIP_MANAGED = "managed"
CONTRACT_MEMBERSHIP_MANAGED_NAME = "Managed"
CONTRACT_MEMBERSHIP_CODE = "code"
CONTRACT_MEMBERSHIP_CODE_NAME = "Enrollment Code"
CONTRACT_MEMBERSHIP_AUTO = "auto"
CONTRACT_MEMBERSHIP_AUTO_NAME = "Auto Enrollment"

CONTRACT_MEMBERSHIP_AUTOS = [
    CONTRACT_MEMBERSHIP_AUTO,
    CONTRACT_MEMBERSHIP_MANAGED,
]

CONTRACT_MEMBERSHIP_TYPE_CHOICES = list(
    zip(
        [
            CONTRACT_MEMBERSHIP_MANAGED,
            CONTRACT_MEMBERSHIP_CODE,
            CONTRACT_MEMBERSHIP_AUTO,
        ],
        [
            CONTRACT_MEMBERSHIP_MANAGED_NAME,
            CONTRACT_MEMBERSHIP_CODE_NAME,
            CONTRACT_MEMBERSHIP_AUTO_NAME,
        ],
    )
)

B2B_RUN_TAG_FORMAT = "{run_idx}T{contract_id}C{year}"

ORG_KEY_MAX_LENGTH = 30

# The holding org/contract that retired course runs get moved into. Runs parked
# here are hidden from every catalog path because the contract is inactive and
# has no members, but the CourseRun row survives - which matters, because
# create_contract_run_key() derives its run index from existing courseware IDs,
# so deleting a retired run risks minting a duplicate courseware ID later.
RETIREMENT_ORG_KEY = "RETIRED"
RETIREMENT_ORG_NAME = "Retired Runs"
RETIREMENT_CONTRACT_NAME = "Retired Runs Holding Contract"

MAILGUN_LOGS_API_URL = "https://api.mailgun.net/v1/analytics/logs"
MAILGUN_LOGS_PAGE_LIMIT = 100
MAILGUN_LOGS_DESC = "timestamp:desc"
# Mailgun only retains log data for 30 days, so there's no point asking further back than that.
MAILGUN_LOGS_RETENTION_DAYS = "30d"
