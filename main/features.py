"""MITxOnline feature flags"""

IGNORE_EDX_FAILURES = "IGNORE_EDX_FAILURES"
SYNC_ON_DASHBOARD_LOAD = "SYNC_ON_DASHBOARD_LOAD"
ENABLE_AUTO_DAILY_FEATURED_ITEMS = "mitxonline-auto-daily-featured-items"
ENABLE_MULTIPLE_CART_ITEMS = "ENABLE_MULTIPLE_CART_ITEMS"

ENABLE_GOOGLE_ANALYTICS_DATA_PUSH = "mitxonline-4099-dedp-google-analytics"

REDIRECT_LEARN_DASHBOARD = "redirect-to-learn-dashboard"

STRIPE_ENABLE_FEATURE_FLAG = "mitxonline-enable-stripe-payments"
ENABLE_PROGRAM_SPECIFIC_PATHWAY_SCHOOLS = (
    "mitxonline-12321-program-specific-pathway-schools"
)
EXPORT_COMPLIANCE_CHECK_ENABLED = "enable_export_compliance"

# Gates the in-progress credential metadata authoring work in the CMS (new
# fields, AI-assisted generation, preview) so each piece can ship incrementally
# without exposing a half-finished workflow to content authors. Does not gate
# the credential fields that already exist and function.
ENABLE_CREDENTIAL_METADATA_AUTHORING = "mitxonline-credential-metadata-authoring"
