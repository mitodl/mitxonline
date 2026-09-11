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

# Onboarding states for a B2B organization, in order. `blocked` is reachable
# from anywhere, with the reason in OrganizationOnboarding.notes.
#
# The state is descriptive, not enforcing: it records what has been observed to
# be true so an operator can answer "what is left for this customer" without
# reading four systems. Nothing in the provisioning API gates on it.
ONBOARDING_STATE_REQUESTED = "requested"
ONBOARDING_STATE_ORG_CREATED = "org_created"
ONBOARDING_STATE_IDP_CONFIGURED = "idp_configured"
ONBOARDING_STATE_IDP_VALIDATED = "idp_validated"
ONBOARDING_STATE_CONTRACT_READY = "contract_ready"
ONBOARDING_STATE_LIVE = "live"
ONBOARDING_STATE_BLOCKED = "blocked"

ONBOARDING_STATE_CHOICES = [
    (ONBOARDING_STATE_REQUESTED, "Requested"),
    (ONBOARDING_STATE_ORG_CREATED, "Organization created"),
    (ONBOARDING_STATE_IDP_CONFIGURED, "Identity provider configured"),
    (ONBOARDING_STATE_IDP_VALIDATED, "Identity provider validated"),
    (ONBOARDING_STATE_CONTRACT_READY, "Contract ready"),
    (ONBOARDING_STATE_LIVE, "Live"),
    (ONBOARDING_STATE_BLOCKED, "Blocked"),
]

IDP_PROTOCOL_SAML = "saml"
IDP_PROTOCOL_OIDC = "oidc"
IDP_PROTOCOL_CHOICES = [
    (IDP_PROTOCOL_SAML, "SAML"),
    (IDP_PROTOCOL_OIDC, "OIDC"),
]

IDP_STATE_DRAFT = "draft"
IDP_STATE_TESTING = "testing"
IDP_STATE_ACTIVE = "active"
IDP_STATE_DISABLED = "disabled"

IDP_LIFECYCLE_CHOICES = [
    (IDP_STATE_DRAFT, "Draft"),
    (IDP_STATE_TESTING, "Testing"),
    (IDP_STATE_ACTIVE, "Active"),
    (IDP_STATE_DISABLED, "Disabled"),
]

# The lifecycle state is written to Keycloak's own `enabled`/`hideOnLogin` as
# well as our row, so the two cannot drift. `hideOnLogin` stays true
# throughout, matching what the Pulumi resources set today: partner IdPs are
# reached by organization/domain routing or an explicit kc_idp_hint, never by a
# button on the shared login page. `testing` and `active` therefore carry the
# same Keycloak flags -- they differ in whether the organization has an
# email-domain redirect pointing at the IdP, which is org-level config.
IDP_STATE_KEYCLOAK_FLAGS = {
    IDP_STATE_DRAFT: {"enabled": False, "hideOnLogin": True},
    IDP_STATE_TESTING: {"enabled": True, "hideOnLogin": True},
    IDP_STATE_ACTIVE: {"enabled": True, "hideOnLogin": True},
    IDP_STATE_DISABLED: {"enabled": False, "hideOnLogin": True},
}

# An IdP goes live only after somebody has actually logged in through it, so
# there is no draft -> active edge. An IdP that has already been through
# testing can be re-enabled directly.
IDP_ALLOWED_TRANSITIONS = {
    IDP_STATE_DRAFT: [IDP_STATE_TESTING],
    IDP_STATE_TESTING: [IDP_STATE_DRAFT, IDP_STATE_ACTIVE, IDP_STATE_DISABLED],
    IDP_STATE_ACTIVE: [IDP_STATE_TESTING, IDP_STATE_DISABLED],
    IDP_STATE_DISABLED: [IDP_STATE_TESTING, IDP_STATE_ACTIVE],
}

MAILGUN_LOGS_API_URL = "https://api.mailgun.net/v1/analytics/logs"
MAILGUN_LOGS_PAGE_LIMIT = 100
MAILGUN_LOGS_DESC = "timestamp:desc"
# Mailgun only retains log data for 30 days, so there's no point asking further back than that.
MAILGUN_LOGS_RETENTION_DAYS = "30d"
