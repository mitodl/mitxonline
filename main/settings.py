# pylint: disable=too-many-lines
"""
Django settings for main.
"""

import logging
import os
import platform
import sys
from datetime import timedelta
from urllib.parse import urljoin, urlparse

import cssutils
import dj_database_url
from celery.schedules import crontab
from django.core.exceptions import ImproperlyConfigured
from mitol.apigateway.settings import *  # noqa: F403  # noqa: F403
from mitol.common.envs import (
    get_bool,
    get_delimited_list,
    get_features,
    get_int,
    get_list_literal,
    get_string,
    import_settings_modules,
)
from mitol.common.settings.celery import *  # noqa: F403
from mitol.google_sheets.settings.google_sheets import *  # noqa: F403
from mitol.google_sheets_deferrals.settings.google_sheets_deferrals import *  # noqa: F403
from mitol.google_sheets_refunds.settings.google_sheets_refunds import *  # noqa: F403
from mitol.scim.settings.scim import *  # noqa: F403
from redbeat import RedBeatScheduler

from main.celery_utils import OffsettingSchedule
from main.env import get_float
from main.sentry import init_sentry
from openapi.settings_spectacular import open_spectacular_settings

VERSION = "0.131.1"

log = logging.getLogger()

# set log level on cssutils - should be fairly high or it will log messages for Outlook-specific styling
cssutils.log.setLevel(logging.CRITICAL)


ENVIRONMENT = get_string(
    name="MITX_ONLINE_ENVIRONMENT",
    default="dev",
    description="The execution environment that the app is in (e.g. dev, staging, prod)",
    required=True,
)
# this is only available to heroku review apps
HEROKU_APP_NAME = get_string(
    name="HEROKU_APP_NAME", default=None, description="The name of the review app"
)

# initialize Sentry before doing anything else so we capture any config errors
SENTRY_DSN = get_string(
    name="SENTRY_DSN", default="", description="The connection settings for Sentry"
)
SENTRY_LOG_LEVEL = get_string(
    name="SENTRY_LOG_LEVEL", default="ERROR", description="The log level for Sentry"
)
SENTRY_TRACES_SAMPLE_RATE = get_float("SENTRY_TRACES_SAMPLE_RATE", 0)
SENTRY_PROFILES_SAMPLE_RATE = get_float("SENTRY_PROFILES_SAMPLE_RATE", 0)
init_sentry(
    dsn=SENTRY_DSN,
    environment=ENVIRONMENT,
    version=VERSION,
    send_default_pii=True,
    log_level=SENTRY_LOG_LEVEL,
    heroku_app_name=HEROKU_APP_NAME,
    traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE,
    profiles_sample_rate=SENTRY_PROFILES_SAMPLE_RATE,
)

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # noqa: PTH100, PTH120

SITE_BASE_URL = get_string(
    name="MITX_ONLINE_BASE_URL",
    default=None,
    description="Base url for the application in the format PROTOCOL://HOSTNAME[:PORT]",
    required=True,
)
MITXONLINE_DOCKER_BASE_URL = get_string(
    name="MITXONLINE_DOCKER_BASE_URL",
    default=None,
    description="Base url for the application when accessed from inside docker containers in the format PROTOCOL://HOSTNAME[:PORT]",
)

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = get_string(
    name="SECRET_KEY", default=None, description="Django secret key.", required=True
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = get_bool(
    name="DEBUG",
    default=False,
    dev_only=True,
    description="Set to True to enable DEBUG mode. Don't turn on in production.",
)

ALLOWED_HOSTS = ["*"]
ALLOWED_REDIRECT_HOSTS = get_list_literal(
    name="ALLOWED_REDIRECT_HOSTS",
    default=[],
    description="List of hosts allowed to redirect to after login",
)

CSRF_COOKIE_DOMAIN = get_string(
    name="CSRF_COOKIE_DOMAIN",
    default=None,
    description="Domain to set the CSRF cookie to.",
)

# NOTE: this is hardcoded in many places so we do not allow it to be dynamic
CSRF_COOKIE_NAME = "csrf_mitxonline"

CSRF_TRUSTED_ORIGINS = get_delimited_list(
    name="CSRF_TRUSTED_ORIGINS",
    default=[],
    description="Comma separated string of trusted domains that should be CSRF exempt",
)

CORS_ALLOWED_ORIGINS = get_delimited_list(
    name="CORS_ALLOWED_ORIGINS",
    default=[],
    description="Comma separated string of trusted domains that should be allowed for CORS",
)

CORS_ALLOW_CREDENTIALS = get_bool(
    name="CORS_ALLOW_CREDENTIALS",
    default=True,
    description="Allow cookies to be sent in cross-site HTTP requests",
)
CORS_ALLOW_HEADERS = (
    # defaults
    "accept",
    "authorization",
    "content-type",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    # sentry tracing
    "baggage",
    "sentry-trace",
)

SESSION_COOKIE_DOMAIN = get_string(
    name="SESSION_COOKIE_DOMAIN",
    default=None,
    description="Domain to set the session cookie to.",
)
SESSION_COOKIE_NAME = get_string(
    name="SESSION_COOKIE_NAME",
    default="mitxonline_sessionid",
    description="Name of the session cookie.",
)

SECURE_SSL_REDIRECT = get_bool(
    name="MITX_ONLINE_SECURE_SSL_REDIRECT",
    default=True,
    description="Application-level SSL redirect setting.",
)

SECURE_REDIRECT_EXEMPT = get_delimited_list(
    name="MITX_ONLINE_SECURE_REDIRECT_EXEMPT",
    default=[
        r"cms/pages/.*",
        r"^health/startup/$",
        r"^health/liveness/$",
        r"^health/readiness/$",
        r"^health/full/$",
    ],
    description="Application-level SSL redirect  exemption setting.",
)

SECURE_SSL_HOST = get_string(
    name="MITX_ONLINE_SECURE_SSL_HOST",
    default=None,
    description="Hostame to redirect non-secure requests to. "
    "Overrides value from HOST header.",
)

WEBPACK_LOADER = {
    "DEFAULT": {
        "CACHE": not DEBUG,
        "STATS_FILE": os.path.join(BASE_DIR, "webpack-stats/default.json"),  # noqa: PTH118
        "POLL_INTERVAL": 0.1,
        "TIMEOUT": None,
        "IGNORE": [r".+\.hot-update\.+", r".+\.js\.map"],
    },
    "STAFF_DASHBOARD": {
        "CACHE": not DEBUG,
        "STATS_FILE": os.path.join(BASE_DIR, "webpack-stats/staff-dashboard.json"),  # noqa: PTH118
        "POLL_INTERVAL": 0.1,
        "TIMEOUT": None,
        "IGNORE": [r".+\.hot-update\.+", r".+\.js\.map"],
    },
}

SITE_ID = get_string(
    name="MITX_ONLINE_SITE_ID",
    default=1,
    description="The default site id for django sites framework",
)

# configure a custom user model
AUTH_USER_MODEL = "users.User"

# Application definition
INSTALLED_APPS = (
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django.contrib.sites",
    "django_user_agents",
    "social_django",
    "oauth2_provider",
    "rest_framework",
    "anymail",
    "django_filters",
    "corsheaders",
    "webpack_loader",
    "django_scim",
    # WAGTAIL
    "wagtail.api.v2",
    "wagtail.contrib.forms",
    "wagtail.contrib.redirects",
    "wagtail.embeds",
    "wagtail.sites",
    "wagtail.snippets",
    "wagtail.documents",
    "wagtail.images",
    "wagtail.search",
    "wagtail.admin",
    "wagtailmetadata",
    "wagtail",
    "modelcluster",
    "taggit",
    "django_object_actions",
    # django-robots
    "robots",
    # django-reversion
    "reversion",
    # django-treebeard
    "treebeard",
    # Put our apps after this point
    "main",
    "authentication",
    "courses",
    "hubspot_sync",
    "mail.apps.MailApp",
    "users",
    "cms.apps.CustomWagtailUsersAppConfig",
    "cms",
    "sheets",
    # "compliance",
    "openedx",
    # must be after "users" to pick up custom user model
    "hijack",
    "hijack.contrib.admin",
    "ecommerce",
    "flexiblepricing",
    "micromasters_import",
    # ol-django apps, must be after this project's apps for template precedence
    "mitol.common.apps.CommonApp",
    "mitol.google_sheets.apps.GoogleSheetsApp",
    "mitol.google_sheets_refunds.apps.GoogleSheetsRefundsApp",
    "mitol.google_sheets_deferrals.apps.GoogleSheetsDeferralsApp",
    # "mitol.digitalcredentials.apps.DigitalCredentialsApp",
    "mitol.hubspot_api",
    "mitol.mail.apps.MailApp",
    "mitol.authentication.apps.TransitionalAuthenticationApp",
    "mitol.payment_gateway.apps.PaymentGatewayApp",
    "mitol.olposthog.apps.OlPosthog",
    "mitol.scim.apps.ScimApp",
    # "mitol.oauth_toolkit_extensions.apps.OAuthToolkitExtensionsApp",
    "viewflow",
    "openapi",
    "drf_spectacular",
    "mitol.apigateway.apps.ApigatewayApp",
    "b2b",
    "health_check",
    "health_check.cache",
    "health_check.contrib.migrations",
    "health_check.contrib.celery_ping",
    "health_check.contrib.redis",
    "health_check.contrib.db_heartbeat",
    "rest_framework_api_key",
)
# Only include the seed data app if this isn't running in prod
# if ENVIRONMENT not in ("production", "prod"):
#     INSTALLED_APPS += ("localdev.seed",)  # noqa: ERA001

HEALTH_CHECK = {
    "SUBSETS": {
        # The 'startup' subset includes checks that must pass before the application can
        # start.
        "startup": [
            "MigrationsHealthCheck",  # Ensures database migrations are applied.
            "CacheBackend",  # Verifies the cache backend is operational.
            "RedisHealthCheck",  # Confirms Redis is reachable and functional.
            "DatabaseHeartBeatCheck",  # Checks the database connection is alive.
        ],
        # The 'liveness' subset includes checks to determine if the application is
        # running.
        "liveness": ["DatabaseHeartBeatCheck"],  # Minimal check to ensure the app is
        # alive.
        # The 'readiness' subset includes checks to determine if the application is
        # ready to serve requests.
        "readiness": [
            "CacheBackend",  # Ensures the cache is ready for use.
            "RedisHealthCheck",  # Confirms Redis is ready for use.
            "DatabaseHeartBeatCheck",  # Verifies the database is ready for queries.
        ],
        # The 'full' subset includes all available health checks for a comprehensive
        # status report.
        "full": [
            "MigrationsHealthCheck",  # Ensures database migrations are applied.
            "CacheBackend",  # Verifies the cache backend is operational.
            "RedisHealthCheck",  # Confirms Redis is reachable and functional.
            "DatabaseHeartBeatCheck",  # Checks the database connection is alive.
            "CeleryPingHealthCheck",  # Verifies Celery workers are responsive.
        ],
    }
}

MIDDLEWARE = (
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "mitol.apigateway.middleware.ApisixUserMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "main.middleware.HostBasedCSRFMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.contrib.sites.middleware.CurrentSiteMiddleware",
    "django_user_agents.middleware.UserAgentMiddleware",
    "hijack.middleware.HijackUserMiddleware",
    "main.middleware.CachelessAPIMiddleware",
    "wagtail.contrib.redirects.middleware.RedirectMiddleware",
    "oauth2_provider.middleware.OAuth2TokenMiddleware",
    "django_scim.middleware.SCIMAuthCheckMiddleware",
)

# enable the nplusone profiler only in debug mode
if DEBUG:
    INSTALLED_APPS += ("nplusone.ext.django",)
    MIDDLEWARE += ("nplusone.ext.django.NPlusOneMiddleware",)

SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"

MITXONLINE_NEW_USER_LOGIN_URL = get_string(
    name="MITXONLINE_NEW_USER_LOGIN_URL",
    default="http://mitxonline.odl.local:8013/create-profile",
    description="URL to redirect new users to after login",
)
LOGIN_REDIRECT_URL = "/"
LOGIN_URL = "/signin"
LOGOUT_REDIRECT_URL = get_string(
    name="LOGOUT_REDIRECT_URL",
    default="/",
    description="Url to redirect to after logout, typically Open edX's own logout url",
)

ROOT_URLCONF = "main.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],  # noqa: PTH118
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "social_django.context_processors.backends",
                "social_django.context_processors.login_redirect",
                "main.context_processors.api_keys",
                "main.context_processors.configuration_context",
            ]
        },
    }
]

WSGI_APPLICATION = "main.wsgi.application"


# Database
# https://docs.djangoproject.com/en/2.0/ref/settings/#databases
DEFAULT_DATABASE_CONFIG = dj_database_url.parse(
    get_string(
        name="DATABASE_URL",
        default="sqlite:///{0}".format(os.path.join(BASE_DIR, "db.sqlite3")),  # noqa: PTH118, UP030
        description="The connection url to the Postgres database",
        required=True,
        write_app_json=False,
    )
)
DEFAULT_DATABASE_CONFIG["CONN_MAX_AGE"] = get_int(
    name="MITX_ONLINE_DB_CONN_MAX_AGE",
    default=0,
    description="Maximum age of connection to Postgres in seconds",
)
# If True, disables server-side database cursors to prevent invalid cursor errors when using pgbouncer
DEFAULT_DATABASE_CONFIG["DISABLE_SERVER_SIDE_CURSORS"] = get_bool(
    name="MITX_ONLINE_DB_DISABLE_SS_CURSORS",
    default=True,
    description="Disables Postgres server side cursors",
)


if get_bool(
    name="MITX_ONLINE_DB_DISABLE_SSL",
    default=False,
    description="Disables SSL to postgres if set to True",
):
    DEFAULT_DATABASE_CONFIG["OPTIONS"] = {}
else:
    DEFAULT_DATABASE_CONFIG["OPTIONS"] = {"sslmode": "require"}

DATABASES = {"default": DEFAULT_DATABASE_CONFIG}

# Internationalization
# https://docs.djangoproject.com/en/2.0/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True


USE_TZ = True

# django-robots
ROBOTS_USE_HOST = False
ROBOTS_CACHE_TIMEOUT = get_int(
    name="ROBOTS_CACHE_TIMEOUT",
    default=60 * 60 * 24,
    description="How long the robots.txt file should be cached",
)

# Social Auth Configuration

AUTHENTICATION_BACKENDS = (
    "authentication.backends.apisix_remote_user_org.ApisixRemoteUserOrgBackend",
    "social_core.backends.email.EmailAuth",
    "oauth2_provider.backends.OAuth2Backend",
    "django.contrib.auth.backends.ModelBackend",
)

SOCIAL_AUTH_LOGIN_ERROR_URL = "login"
SOCIAL_AUTH_ALLOWED_REDIRECT_HOSTS = [urlparse(SITE_BASE_URL).netloc]
SOCIAL_AUTH_IMMUTABLE_USER_FIELDS = [
    "global_id",
]

# Email backend settings

SOCIAL_AUTH_EMAIL_FORM_URL = "login"
SOCIAL_AUTH_EMAIL_FORM_HTML = "login.html"

SOCIAL_AUTH_EMAIL_USER_FIELDS = ["username", "email", "name", "password"]

# Only validate emails for the email backend
SOCIAL_AUTH_EMAIL_FORCE_EMAIL_VALIDATION = True

# Configure social_core.pipeline.mail.mail_validation
SOCIAL_AUTH_EMAIL_VALIDATION_FUNCTION = "mail.verification_api.send_verification_email"
SOCIAL_AUTH_EMAIL_VALIDATION_URL = "/"

SOCIAL_AUTH_PIPELINE = (
    # Checks if an admin user attempts to login/register while hijacking another user.
    "authentication.pipeline.user.forbid_hijack",
    # Get the information we can about the user and return it in a simple
    # format to create the user instance later. On some cases the details are
    # already part of the auth response from the provider, but sometimes this
    # could hit a provider API.
    "social_core.pipeline.social_auth.social_details",
    # Get the social uid from whichever service we're authing thru. The uid is
    # the unique identifier of the given user in the provider.
    "social_core.pipeline.social_auth.social_uid",
    # Verifies that the current auth process is valid within the current
    # project, this is where emails and domains whitelists are applied (if
    # defined).
    "social_core.pipeline.social_auth.auth_allowed",
    # Checks if the current social-account is already associated in the site.
    "social_core.pipeline.social_auth.social_user",
    # Associates the current social details with another user account with the same email address.
    "social_core.pipeline.social_auth.associate_by_email",
    # validate an incoming email auth request
    "authentication.pipeline.user.validate_email_auth_request",
    # validate the user's email either it is blocked or not.
    "authentication.pipeline.user.validate_email",
    # require a password and profile if they're not set
    "authentication.pipeline.user.validate_password",
    # Send a validation email to the user to verify its email address.
    # Disabled by default.
    "social_core.pipeline.mail.mail_validation",
    # Send the email address and hubspot cookie if it exists to hubspot.
    # "authentication.pipeline.user.send_user_to_hubspot",
    # Generate a username for the user
    # NOTE: needs to be right before create_user so nothing overrides the username
    "authentication.pipeline.user.get_username",
    # Create a user if one doesn't exist, and require a password and name
    "authentication.pipeline.user.create_user_via_email",
    # If we're using the OIDC backend, create the user from the OIDC response
    "authentication.pipeline.user.create_ol_oidc_user",
    # verify the user against export compliance
    # "authentication.pipeline.compliance.verify_exports_compliance",
    # Create the record that associates the social account with the user.
    "social_core.pipeline.social_auth.associate_user",
    # create the user's edx user and auth
    "authentication.pipeline.user.create_openedx_user",
    # Populate the extra_data field in the social record with the values
    # specified by settings (and the default ones like access_token, etc).
    "social_core.pipeline.social_auth.load_extra_data",
    # Update the user record with any changed info from the auth service.
    "social_core.pipeline.user.user_details",
)


# Social Auth OIDC configuration

SOCIAL_AUTH_OL_OIDC_OIDC_ENDPOINT = get_string(
    name="SOCIAL_AUTH_OL_OIDC_OIDC_ENDPOINT",
    default=None,
    description="The configuration endpoint for the OIDC provider",
)

SOCIAL_AUTH_OL_OIDC_KEY = get_string(
    name="SOCIAL_AUTH_OL_OIDC_KEY",
    default="some available client id",
    description="The client id for the OIDC provider",
)

SOCIAL_AUTH_OL_OIDC_SECRET = get_string(
    name="SOCIAL_AUTH_OL_OIDC_SECRET",
    default="some super secret key",
    description="The client secret for the OIDC provider",
)

SOCIAL_AUTH_OL_OIDC_SCOPE = ["ol-profile"]

AUTH_CHANGE_EMAIL_TTL_IN_MINUTES = get_int(
    name="AUTH_CHANGE_EMAIL_TTL_IN_MINUTES",
    default=60 * 24,
    description="Expiry time for a change email request, default is 1440 minutes(1 day)",
)

# Disable the OIDC button on the signin screen.
# Doesn't actually disable OIDC login - you can still go to /login/ol-oidc/
# (assuming OIDC is set up).
EXPOSE_OIDC_LOGIN = get_bool(
    name="EXPOSE_OIDC_LOGIN",
    default=False,
    description="Expose the OIDC login functionality.",
)

# These are used for logout.
KEYCLOAK_BASE_URL = get_string(
    name="KEYCLOAK_BASE_URL",
    default="http://mit-keycloak-base-url.edu",
    description="Base URL for the Keycloak instance.",
)

KEYCLOAK_REALM_NAME = get_string(
    name="KEYCLOAK_REALM_NAME",
    default="olapps",
    description="Name of the realm the app uses in Keycloak.",
)

KEYCLOAK_CLIENT_ID = get_string(
    name="KEYCLOAK_CLIENT_ID",
    default=None,
    description="The client name for mitxonline.",
)

KEYCLOAK_CLIENT_SECRET = get_string(
    name="KEYCLOAK_CLIENT_SECRET",
    default=None,
    description="The client secret for mitxonline.",
)

KEYCLOAK_DISCOVERY_URL = get_string(
    name="KEYCLOAK_DISCOVERY_URL",
    default=None,
    description="The OpenID discovery URL for the Keycloak realm.",
)

KEYCLOAK_ADMIN_CLIENT_ID = get_string(
    name="KEYCLOAK_ADMIN_CLIENT_ID",
    default=None,
    description="The client name for the admin client.",
)

KEYCLOAK_ADMIN_CLIENT_SECRET = get_string(
    name="KEYCLOAK_ADMIN_CLIENT_SECRET",
    default=None,
    description="The client secret for the admin client.",
)

KEYCLOAK_ADMIN_CLIENT_SCOPES = get_string(
    name="KEYCLOAK_ADMIN_CLIENT_SCOPES",
    default=None,
    description="The OpenID scopes to use for the admin client.",
)

KEYCLOAK_ADMIN_CLIENT_NO_VERIFY_SSL = get_bool(
    name="KEYCLOAK_ADMIN_CLIENT_NO_VERIFY_SSL",
    default=False,
    description="If true, do not verify SSL certificates for the admin client.",
)

# Social Auth Configuration end

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.8/howto/static-files/

# Serve static files with dj-static
STATIC_URL = "/static/"
CLOUDFRONT_DIST = get_string(
    name="CLOUDFRONT_DIST",
    default=None,
    description="The Cloundfront distribution to use for static assets",
)
if CLOUDFRONT_DIST:
    STATIC_URL = urljoin(f"https://{CLOUDFRONT_DIST}.cloudfront.net", STATIC_URL)

STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]

STATIC_ROOT = "staticfiles"
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "static"),  # noqa: PTH118
]
for name, path in [
    ("mitx-online", os.path.join(BASE_DIR, "frontend/public/build")),  # noqa: PTH118
    (
        "staff-dashboard",
        os.path.join(BASE_DIR, "frontend/staff-dashboard/build"),  # noqa: PTH118
    ),
]:
    if os.path.exists(path):  # noqa: PTH110
        STATICFILES_DIRS.append((name, path))
    elif not ("pytest" in sys.modules or "test" in sys.argv):
        # Only log warning if we're not running tests
        log.warning(f"Static file directory was missing: {path}")  # noqa: G004

# Important to define this so DEBUG works properly
INTERNAL_IPS = (
    get_string(
        name="HOST_IP", default="127.0.0.1", description="This server's host IP"
    ),
)

# Configure e-mail settings
EMAIL_BACKEND = get_string(
    name="MITX_ONLINE_EMAIL_BACKEND",
    default="django.core.mail.backends.smtp.EmailBackend",
    description="The default email backend to use for outgoing email. This is used in some places by django itself. See `NOTIFICATION_EMAIL_BACKEND` for the backend used for most application emails.",
)
EMAIL_HOST = get_string(
    name="MITX_ONLINE_EMAIL_HOST",
    default="localhost",
    description="Outgoing e-mail hostname",
)
EMAIL_PORT = get_int(
    name="MITX_ONLINE_EMAIL_PORT", default=25, description="Outgoing e-mail port"
)
EMAIL_HOST_USER = get_string(
    name="MITX_ONLINE_EMAIL_USER",
    default="",
    description="Outgoing e-mail auth username",
)
EMAIL_HOST_PASSWORD = get_string(
    name="MITX_ONLINE_EMAIL_PASSWORD",
    default="",
    description="Outgoing e-mail auth password",
)
EMAIL_USE_TLS = get_bool(
    name="MITX_ONLINE_EMAIL_TLS",
    default=False,
    description="Outgoing e-mail TLS setting",
)

DEFAULT_FROM_EMAIL = get_string(
    name="MITX_ONLINE_FROM_EMAIL",
    default="webmaster@localhost",
    description="E-mail to use for the from field",
)

MITX_ONLINE_REPLY_TO_ADDRESS = get_string(
    name="MITX_ONLINE_REPLY_TO_ADDRESS",
    default=DEFAULT_FROM_EMAIL,
    description="E-mail to use for reply-to address of emails",
)

MAILGUN_FROM_EMAIL = DEFAULT_FROM_EMAIL
MAILGUN_SENDER_DOMAIN = get_string(
    name="MAILGUN_SENDER_DOMAIN",
    default=None,
    description="The domain to send mailgun email through",
    required=True,
)
MAILGUN_KEY = get_string(
    name="MAILGUN_KEY",
    default=None,
    description="The token for authenticating against the Mailgun API",
    required=True,
)
MAILGUN_BATCH_CHUNK_SIZE = get_int(
    name="MAILGUN_BATCH_CHUNK_SIZE",
    default=1000,
    description="Maximum number of emails to send in a batch",
)
MAILGUN_RECIPIENT_OVERRIDE = get_string(
    name="MAILGUN_RECIPIENT_OVERRIDE",
    default=None,
    dev_only=True,
    description="Override the recipient for outgoing email, development only",
)

EMAIL_SUPPORT = get_string(
    name="MITX_ONLINE_SUPPORT_EMAIL",
    default=MAILGUN_RECIPIENT_OVERRIDE or "support@localhost",
    description="Email address listed for customer support in the frontend. Not used for sending email.",
)

NOTIFICATION_EMAIL_BACKEND = get_string(
    name="MITX_ONLINE_NOTIFICATION_EMAIL_BACKEND",
    default="anymail.backends.mailgun.EmailBackend",
    description="The email backend to use for application emails",
)

ANYMAIL = {
    "MAILGUN_API_KEY": MAILGUN_KEY,
    "MAILGUN_SENDER_DOMAIN": MAILGUN_SENDER_DOMAIN,
}

# e-mail configurable admins
ADMIN_EMAIL = get_string(
    name="MITX_ONLINE_ADMIN_EMAIL",
    default="",
    description="E-mail to send 500 reports to.",
    required=True,
)
if ADMIN_EMAIL != "":  # noqa: SIM108
    ADMINS = (("Admins", ADMIN_EMAIL),)
else:
    ADMINS = ()

MIT_LEARN_FROM_EMAIL = get_string(
    name="MIT_LEARN_FROM_EMAIL",
    default="MIT Learn <mitlearn-support@mit.edu>",
    description="From email address for UAI enrollment emails",
)

MIT_LEARN_REPLY_TO_EMAIL = get_string(
    name="MIT_LEARN_REPLY_TO_EMAIL",
    default=MIT_LEARN_FROM_EMAIL,
    description="Reply-to email address for UAI enrollment emails (defaults to MIT_LEARN_FROM_EMAIL)",
)

MIT_LEARN_DASHBOARD_URL = get_string(
    name="MIT_LEARN_DASHBOARD_URL",
    default="https://learn.mit.edu/dashboard",
    description="Dashboard URL for UAI enrollment emails",
)

# Logging configuration
LOG_LEVEL = get_string(
    name="MITX_ONLINE_LOG_LEVEL", default="INFO", description="The log level default"
)
DJANGO_LOG_LEVEL = get_string(
    name="DJANGO_LOG_LEVEL", default="INFO", description="The log level for django"
)

HOSTNAME = platform.node().split(".")[0]

# nplusone profiler logger configuration
NPLUSONE_LOGGER = logging.getLogger("nplusone")
NPLUSONE_LOG_LEVEL = logging.ERROR

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"require_debug_false": {"()": "django.utils.log.RequireDebugFalse"}},
    "formatters": {
        "verbose": {
            "format": (
                "[%(asctime)s] %(levelname)s %(process)d [%(name)s] "
                "%(filename)s:%(lineno)d - "
                f"[{HOSTNAME}] - %(message)s"
            ),
            "datefmt": "%Y-%m-%d %H:%M:%S",
        }
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "mail_admins": {
            "level": "ERROR",
            "filters": ["require_debug_false"],
            "class": "django.utils.log.AdminEmailHandler",
        },
    },
    "loggers": {
        "django": {
            "propagate": True,
            "level": DJANGO_LOG_LEVEL,
            "handlers": ["console"],
        },
        "django.request": {
            "handlers": ["mail_admins"],
            "level": DJANGO_LOG_LEVEL,
            "propagate": True,
        },
        "nplusone": {"handlers": ["console"], "level": "ERROR"},
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
}

# server-status
STATUS_TOKEN = get_string(
    name="STATUS_TOKEN", default="", description="Token to access the status API."
)

GTM_TRACKING_ID = get_string(
    name="GTM_TRACKING_ID", default="", description="Google Tag Manager container ID"
)
GA_TRACKING_ID = get_string(
    name="GA_TRACKING_ID", default="", description="Google analytics tracking ID"
)
REACT_GA_DEBUG = get_bool(
    name="REACT_GA_DEBUG",
    default=False,
    dev_only=True,
    description="Enable debug for react-ga, development only",
)

RECAPTCHA_SITE_KEY = get_string(
    name="RECAPTCHA_SITE_KEY", default="", description="The ReCaptcha site key"
)
RECAPTCHA_SECRET_KEY = get_string(
    name="RECAPTCHA_SECRET_KEY", default="", description="The ReCaptcha secret key"
)

USE_X_FORWARDED_HOST = get_bool(
    name="USE_X_FORWARDED_HOST",
    default=False,
    description="Set HOST header to original domain accessed by user",
)
SITE_NAME = get_string(
    name="SITE_NAME",
    default="MITx Online",
    description="Name of the site. e.g MITx Online",
)
WAGTAIL_SITE_NAME = SITE_NAME

WAGTAILSEARCH_BACKENDS = {
    "default": {
        "BACKEND": "wagtail.search.backends.database",
        "ATOMIC_REBUILD": True,
    },
}

WAGTAILADMIN_BASE_URL = SITE_BASE_URL

MEDIA_ROOT = get_string(
    name="MEDIA_ROOT",
    default="/var/media/",
    description="The root directory for locally stored media. Typically not used.",
)
MEDIA_URL = "/media/"
MITX_ONLINE_USE_S3 = get_bool(
    name="MITX_ONLINE_USE_S3",
    default=False,
    description="Use S3 for storage backend (required on Heroku)",
)

AWS_ACCESS_KEY_ID = get_string(
    name="AWS_ACCESS_KEY_ID", default=None, description="AWS Access Key for S3 storage."
)
AWS_SECRET_ACCESS_KEY = get_string(
    name="AWS_SECRET_ACCESS_KEY",
    default=None,
    description="AWS Secret Key for S3 storage.",
)
AWS_STORAGE_BUCKET_NAME = get_string(
    name="AWS_STORAGE_BUCKET_NAME", default=None, description="S3 Bucket name."
)
AWS_QUERYSTRING_AUTH = get_bool(
    name="AWS_QUERYSTRING_AUTH",
    default=False,
    description="Enables querystring auth for S3 urls",
)
AWS_S3_FILE_OVERWRITE = get_bool(
    name="AWS_S3_FILE_OVERWRITE",
    # Django Storages defaults this setting to True, but our desired default is False to avoid name collisions in
    # files uploaded in the CMS.
    default=False,
    description=(
        "Django Storages setting. By default files with the same name will overwrite each other. "
        "Set this to False to have extra characters appended."
    ),
)
# Provide nice validation of the configuration
if MITX_ONLINE_USE_S3 and (
    not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY or not AWS_STORAGE_BUCKET_NAME
):
    raise ImproperlyConfigured(
        "You have enabled S3 support, but are missing one of "  # noqa: EM101
        "AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, or "
        "AWS_STORAGE_BUCKET_NAME"
    )
if MITX_ONLINE_USE_S3:
    if CLOUDFRONT_DIST:
        AWS_S3_CUSTOM_DOMAIN = f"{CLOUDFRONT_DIST}.cloudfront.net"
    DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"

FEATURES_DEFAULT = get_bool(
    name="FEATURES_DEFAULT",
    default=False,
    dev_only=True,
    description="The default value for all feature flags",
)
FEATURES = get_features()

# Redis
REDISCLOUD_URL = get_string(
    name="REDISCLOUD_URL", default=None, description="RedisCloud connection url"
)
if REDISCLOUD_URL is not None:
    _redis_url = REDISCLOUD_URL
else:
    _redis_url = get_string(
        name="REDIS_URL", default=None, description="Redis URL for non-production use"
    )
# Use the more consistently looked-for name to support healthchecks package
REDIS_URL = _redis_url

# Celery
USE_CELERY = True
CELERY_BROKER_URL = get_string(
    name="CELERY_BROKER_URL",
    default=_redis_url,
    description="Where celery should get tasks, default is Redis URL",
)
CELERY_RESULT_BACKEND = get_string(
    name="CELERY_RESULT_BACKEND",
    default=_redis_url,
    description="Where celery should put task results, default is Redis URL",
)
CELERY_BEAT_SCHEDULER = RedBeatScheduler
CELERY_REDBEAT_REDIS_URL = _redis_url
CELERY_TASK_ALWAYS_EAGER = get_bool(
    name="CELERY_TASK_ALWAYS_EAGER",
    default=False,
    dev_only=True,
    description="Enables eager execution of celery tasks, development only",
)
CELERY_TASK_EAGER_PROPAGATES = get_bool(
    name="CELERY_TASK_EAGER_PROPAGATES",
    default=True,
    description="Early executed tasks propagate exceptions",
)
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = "UTC"
CELERY_CREATE_MISSING_QUEUES = True
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_SEND_SENT_EVENT = True
CRON_COURSERUN_SYNC_HOURS = get_string(
    name="CRON_COURSERUN_SYNC_HOURS",
    default=0,
    description="'hours' value for scheduled task to sync course run data (by default, it will run at midnight",
)
CRON_COURSERUN_SYNC_DAYS = get_string(
    name="CRON_COURSERUN_SYNC_DAYS",
    default="*",
    description="day_of_week' value for scheduled task to sync course run data (by default, it will run each day of the week).",
)
CRON_PROCESS_REFUND_REQUESTS_MINUTES = get_string(
    name="CRON_PROCESS_REFUND_REQUESTS_MINUTES",
    default="*",
    description="minute value for scheduled task to process refund requests",
)
CRON_COURSE_CERTIFICATES_HOURS = get_string(
    name="CRON_COURSE_CERTIFICATES_HOURS",
    default="0,12",
    description="'hours' value for the 'generate-course-certificate' scheduled task (defaults to midnight)",
)
CRON_COURSE_CERTIFICATES_DAYS = get_string(
    name="CRON_COURSE_CERTIFICATES_DAYS",
    default="*",
    description="'day_of_week' value for 'generate-course-certificate' scheduled task (default will run once a day).",
)
CRON_ORPHAN_CHECK_HOURS = get_string(
    name="CRON_ORPHAN_CHECK_HOURS",
    default="3",
    description="'hours' value for 'check-for-program-orphans' scheduled task (default will run at 3 AM).",
)
CRON_ORPHAN_CHECK_DAYS = get_string(
    name="CRON_ORPHAN_CHECK_DAYS",
    default="*",
    description="'day_of_week' value for 'check-for-program-orphans' scheduled task (default will run once a day).",
)

CERTIFICATE_CREATION_WINDOW_IN_DAYS = get_int(
    name="CERTIFICATE_CREATION_WINDOW_IN_DAYS",
    default=31,
    description="The number of days a course run is eligible for certificate creation after it ends.",
)

RETRY_FAILED_EDX_ENROLLMENT_FREQUENCY = get_int(
    name="RETRY_FAILED_EDX_ENROLLMENT_FREQUENCY",
    default=60 * 30,
    description="How many seconds between retrying failed edX enrollments",
)
REPAIR_OPENEDX_USERS_FREQUENCY = get_int(
    name="REPAIR_OPENEDX_USERS_FREQUENCY",
    default=60 * 30,
    description="How many seconds between repairing openedx records for faulty users",
)
REPAIR_OPENEDX_USERS_OFFSET = int(REPAIR_OPENEDX_USERS_FREQUENCY / 2)

REFRESH_FEATURED_HOMEPAGE_ITEMS_FREQ = get_int(
    name="REFRESH_FEATURED_HOMEPAGE_ITEMS_FREQ",
    default=86400,
    description="How many seconds between refreshing featured items for the homepage cache",
)

REFRESH_FEATURED_HOMEPAGE_ITEMS_OFFSET = int(REFRESH_FEATURED_HOMEPAGE_ITEMS_FREQ / 2)

KEYCLOAK_ORG_SYNC_FREQUENCY = get_int(
    name="KEYCLOAK_ORG_SYNC_FREQUENCY",
    default=86400,
    description="How many seconds to wait between refreshing organization data from the Keycloak API",
)

KEYCLOAK_ORG_SYNC_OFFSET = get_int(
    name="KEYCLOAK_ORG_SYNC_OFFSET",
    default=int(KEYCLOAK_ORG_SYNC_FREQUENCY / 2),
    description="Offset for the Keycloak org sync",
)

CELERY_BEAT_SCHEDULE = {
    "retry-failed-edx-enrollments": {
        "task": "openedx.tasks.retry_failed_edx_enrollments",
        "schedule": RETRY_FAILED_EDX_ENROLLMENT_FREQUENCY,
    },
    "update-currency-exchange-rates-every-24-hrs": {
        "task": "flexiblepricing.tasks.sync_currency_exchange_rates",
        "schedule": crontab(minute=0, hour="3"),
    },
    "repair-faulty-edx-users": {
        "task": "openedx.tasks.repair_faulty_openedx_users",
        "schedule": OffsettingSchedule(
            run_every=timedelta(seconds=REPAIR_OPENEDX_USERS_FREQUENCY),
            offset=timedelta(seconds=REPAIR_OPENEDX_USERS_OFFSET),
        ),
    },
    "sync-courseruns-data": {
        "task": "courses.tasks.sync_courseruns_data",
        "schedule": crontab(
            minute=0,
            hour=CRON_COURSERUN_SYNC_HOURS,
            day_of_week=CRON_COURSERUN_SYNC_DAYS,
            day_of_month="*",
            month_of_year="*",
        ),
    },
    "process-google-sheets-requests": {
        "task": "sheets.tasks.process_google_sheets_requests",
        "schedule": crontab(minute=CRON_PROCESS_REFUND_REQUESTS_MINUTES, hour="10-2"),
    },
    "generate-course-certificate": {
        "task": "courses.tasks.generate_course_certificates",
        "schedule": crontab(
            minute=0,
            hour=CRON_COURSE_CERTIFICATES_HOURS,
            day_of_week=CRON_COURSE_CERTIFICATES_DAYS,
            day_of_month="*",
            month_of_year="*",
        ),
    },
    "refresh-featured-homepage-items": {
        "task": "cms.tasks.refresh_featured_homepage_items",
        "schedule": OffsettingSchedule(
            run_every=timedelta(seconds=REFRESH_FEATURED_HOMEPAGE_ITEMS_FREQ),
            offset=timedelta(seconds=REFRESH_FEATURED_HOMEPAGE_ITEMS_OFFSET),
        ),
    },
    "sync-keycloak": {
        "task": "b2b.tasks.queue_organization_sync",
        "schedule": OffsettingSchedule(
            run_every=timedelta(seconds=KEYCLOAK_ORG_SYNC_FREQUENCY),
            offset=timedelta(seconds=KEYCLOAK_ORG_SYNC_OFFSET),
        ),
    },
}

# Hijack
HIJACK_ALLOW_GET_REQUESTS = True
HIJACK_LOGOUT_REDIRECT_URL = "/admin/users/user"
HIJACK_REGISTER_ADMIN = False

# django cache back-ends
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "local-in-memory-cache",
    },
    "redis": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": CELERY_BROKER_URL,
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
    },
    "durable": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "durable_cache",
    },
}

# required for migrations
OAUTH2_PROVIDER_ACCESS_TOKEN_MODEL = "oauth2_provider.AccessToken"  # noqa: S105
OAUTH2_PROVIDER_APPLICATION_MODEL = "oauth2_provider.Application"
OAUTH2_PROVIDER_REFRESH_TOKEN_MODEL = "oauth2_provider.RefreshToken"  # noqa: S105

OAUTH2_PROVIDER = {
    "OIDC_ENABLED": True,
    "OIDC_RSA_PRIVATE_KEY": get_string(
        name="OIDC_RSA_PRIVATE_KEY",
        default=None,
        description="RSA private key for OIDC",
    ),
    # this is the list of available scopes
    "SCOPES": {
        "read": "Read scope",
        "write": "Write scope",
        "openid": "OpenID Connect scope",
        "user:read": "Can read user and profile data",
        # "digitalcredentials": "Can read and write Digital Credentials data",  # noqa: ERA001
    },
    "DEFAULT_SCOPES": ["user:read"],
    "OAUTH2_VALIDATOR_CLASS": "main.oidc_provider_settings.CustomOAuth2Validator",
    # "SCOPES_BACKEND_CLASS": "mitol.oauth_toolkit_extensions.backends.ApplicationAccessOrSettingsScopes",  # noqa: ERA001
    "ERROR_RESPONSE_WITH_SCOPES": DEBUG,
    "ALLOWED_REDIRECT_URI_SCHEMES": get_delimited_list(
        name="OAUTH2_PROVIDER_ALLOWED_REDIRECT_URI_SCHEMES",
        default=["http", "https"],
        description="List of schemes allowed for oauth2 redirect URIs",
    ),
}

SCIM_SERVICE_PROVIDER["USER_ADAPTER"] = "users.adapters.LearnUserAdapter"  # noqa: F405

# DRF configuration
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.SessionAuthentication",
        "oauth2_provider.contrib.rest_framework.OAuth2Authentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "EXCEPTION_HANDLER": "main.exceptions.exception_handler",
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
    "DEFAULT_VERSIONING": "rest_framework.versioning.NamespaceVersioning",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "ALLOWED_VERSIONS": ["v0", "v1", "v2"],
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",)
    if not DEBUG
    else (
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ),
}

# Relative URL to be used by Djoser for the link in the password reset email
# (see: http://djoser.readthedocs.io/en/stable/settings.html#password-reset-confirm-url)
PASSWORD_RESET_CONFIRM_URL = "password_reset/confirm/{uid}/{token}/"  # noqa: S105

# ol-django configuration

import_settings_modules(
    "mitol.authentication.settings.djoser_settings",
    "mitol.payment_gateway.settings.cybersource",
)

# mitol-django-common
MITOL_COMMON_USER_FACTORY = "users.factories.UserFactory"

# mitol-django-mail
MITOL_MAIL_FROM_EMAIL = MAILGUN_FROM_EMAIL
MITOL_MAIL_REPLY_TO_ADDRESS = MITX_ONLINE_REPLY_TO_ADDRESS
MITOL_MAIL_MESSAGE_CLASSES = []
MITOL_MAIL_RECIPIENT_OVERRIDE = MAILGUN_RECIPIENT_OVERRIDE
MITOL_MAIL_FORMAT_RECIPIENT_FUNC = "users.utils.format_recipient"
MITOL_MAIL_ENABLE_EMAIL_DEBUGGER = get_bool(  # NOTE: this will override the legacy mail debugger defined in this project
    name="MITOL_MAIL_ENABLE_EMAIL_DEBUGGER",
    default=False,
    description="Enable the mitol-mail email debugger",
    dev_only=True,
)

# mitol-django-authentication
MITOL_AUTHENTICATION_FROM_EMAIL = MAILGUN_FROM_EMAIL
MITOL_AUTHENTICATION_REPLY_TO_EMAIL = MITX_ONLINE_REPLY_TO_ADDRESS

OPENEDX_OAUTH_PROVIDER = get_string(
    name="OPENEDX_OAUTH_PROVIDER",
    default="mitxpro-oauth2",
    description="Social auth provider backend name",
)

OPENEDX_SOCIAL_LOGIN_PATH = get_string(
    name="OPENEDX_SOCIAL_LOGIN_PATH",
    default="/auth/login/mitxpro-oauth2/?auth_entry=login",
    description="Open edX social auth login url",
)

OPENEDX_OAUTH_APP_NAME = get_string(
    name="OPENEDX_OAUTH_APP_NAME",
    default="edx-oauth-app",
    required=True,
    description="The 'name' value for the Open edX OAuth Application",
)
OPENEDX_API_BASE_URL = get_string(
    name="OPENEDX_API_BASE_URL",
    default="http://edx.odl.local:18000",
    description="The base URL for the Open edX API",
    required=True,
)
OPENEDX_STUDIO_API_BASE_URL = get_string(
    name="OPENEDX_STUDIO_API_BASE_URL",
    default="http://studio.edx.odl.local:18001",
    description="The base URL for the Open edX Studio CMS API",
    required=True,
)
OPENEDX_COURSE_BASE_URL = get_string(
    name="OPENEDX_COURSE_BASE_URL",
    default="http://edx.odl.local:18000/learn/course/",
    description="The base URL to use to construct URLs to a course",
)

OPENEDX_BASE_REDIRECT_URL = get_string(
    name="OPENEDX_BASE_REDIRECT_URL",
    default=OPENEDX_API_BASE_URL,
    description="The base redirect URL for an OAuth Application for the Open edX API",
)
OPENEDX_TOKEN_EXPIRES_HOURS = get_int(
    name="OPENEDX_TOKEN_EXPIRES_HOURS",
    default=1000,
    description="The number of hours until an access token for the Open edX API expires",
)
OPENEDX_API_CLIENT_ID = get_string(
    name="OPENEDX_API_CLIENT_ID",
    default=None,
    description="The OAuth2 client id to connect to Open edX with",
    required=True,
)
OPENEDX_API_CLIENT_SECRET = get_string(
    name="OPENEDX_API_CLIENT_SECRET",
    default=None,
    description="The OAuth2 client secret to connect to Open edX with",
    required=True,
)

MITX_ONLINE_REGISTRATION_ACCESS_TOKEN = get_string(
    name="MITX_ONLINE_REGISTRATION_ACCESS_TOKEN",
    default=None,
    description="Access token to secure Open edX registration API with",
)

OPENEDX_SERVICE_WORKER_API_TOKEN = get_string(
    name="OPENEDX_SERVICE_WORKER_API_TOKEN",
    default=None,
    description="Active access token with staff level permissions to use with OpenEdX API client for service tasks",
)
OPENEDX_SERVICE_WORKER_USERNAME = get_string(
    name="OPENEDX_SERVICE_WORKER_USERNAME",
    default=None,
    description="Username of the user whose token has been set in OPENEDX_SERVICE_WORKER_API_TOKEN",
)

OPENEDX_RETIREMENT_SERVICE_WORKER_CLIENT_ID = get_string(
    name="OPENEDX_RETIREMENT_SERVICE_WORKER_CLIENT_ID",
    default=None,
    description="OAuth2 client id for retirement service worker",
)
OPENEDX_RETIREMENT_SERVICE_WORKER_CLIENT_SECRET = get_string(
    name="OPENEDX_RETIREMENT_SERVICE_WORKER_CLIENT_SECRET",
    default=None,
    description="OAuth2 client secret for retirement service worker",
)

OPENEDX_COURSES_SERVICE_WORKER_CLIENT_ID = get_string(
    name="OPENEDX_COURSES_SERVICE_WORKER_CLIENT_ID",
    default=OPENEDX_API_CLIENT_ID,
    description="OAuth2 client id for retirement service worker",
)
OPENEDX_COURSES_SERVICE_WORKER_CLIENT_SECRET = get_string(
    name="OPENEDX_COURSES_SERVICE_WORKER_CLIENT_SECRET",
    default=OPENEDX_API_CLIENT_SECRET,
    description="OAuth2 client secret for retirement service worker",
)

EDX_API_CLIENT_TIMEOUT = get_int(
    name="EDX_API_CLIENT_TIMEOUT",
    default=60,
    description="Timeout (in seconds) for requests made via the edX API client",
)

# django debug toolbar only in debug mode
if DEBUG:
    INSTALLED_APPS += ("debug_toolbar",)
    # it needs to be enabled before other middlewares
    MIDDLEWARE = ("debug_toolbar.middleware.DebugToolbarMiddleware",) + MIDDLEWARE  # noqa: RUF005

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"


# Open Exchange Rates
OPEN_EXCHANGE_RATES_URL = get_string(
    name="OPEN_EXCHANGE_RATES_URL",
    default="https://openexchangerates.org/api/",
    description="open exchange api url for fetching currency exchange rate",
)
OPEN_EXCHANGE_RATES_APP_ID = get_string(
    name="OPEN_EXCHANGE_RATES_APP_ID",
    default="",
    description="open exchange app id for fetching currency exchange rate",
)

MITX_ONLINE_REFINE_OIDC_CONFIG_CLIENT_ID = get_string(
    name="MITX_ONLINE_REFINE_OIDC_CONFIG_CLIENT_ID",
    default=None,
    description="open exchange app id for fetching currency exchange rate",
)
MITX_ONLINE_REFINE_OIDC_CONFIG_AUTHORITY = get_string(
    name="MITX_ONLINE_REFINE_OIDC_CONFIG_AUTHORITY",
    default=urljoin(SITE_BASE_URL, "/oauth2/"),
    description="open exchange app id for fetching currency exchange rate",
)
MITX_ONLINE_REFINE_OIDC_CONFIG_REDIRECT_URI = get_string(
    name="MITX_ONLINE_REFINE_OIDC_CONFIG_REDIRECT_URI",
    default=urljoin(SITE_BASE_URL, "/staff-dashboard/oauth2/login/"),
    description="Url to redirect the user to",
)
MITX_ONLINE_REFINE_MITX_ONLINE_DATASOURCE = get_string(
    name="MITX_ONLINE_REFINE_MITX_ONLINE_DATASOURCE",
    default=urljoin(SITE_BASE_URL, "/api"),
    description="open exchange app id for fetching currency exchange rate",
)
GOOGLE_DOMAIN_VERIFICATION_TAG_VALUE = get_string(
    name="GOOGLE_DOMAIN_VERIFICATION_TAG_VALUE",
    default=None,
    description="The value of the meta tag used by Google to verify the owner of a domain (used for enabling push notifications)",
)

MITOL_GOOGLE_SHEETS_REFUNDS_PLUGINS = ["sheets.refunds_plugin.RefundPlugin"]
MITOL_GOOGLE_SHEETS_DEFERRALS_PLUGINS = ["sheets.deferrals_plugin.DeferralPlugin"]


# Fastly configuration
MITX_ONLINE_FASTLY_AUTH_TOKEN = get_string(
    name="FASTLY_AUTH_TOKEN",
    default=None,
    description="Optional token for the Fastly purge API.",
)

MITX_ONLINE_FASTLY_URL = get_string(
    name="FASTLY_URL",
    default="https://api.fastly.com",
    description="The URL to the Fastly API.",
)

# Hubspot sync settings
MITOL_HUBSPOT_API_PRIVATE_TOKEN = get_string(
    name="MITOL_HUBSPOT_API_PRIVATE_TOKEN",
    default=None,
    description="Hubspot private token to authenticate with API",
)
MITOL_HUBSPOT_API_RETRIES = get_int(
    name="MITOL_HUBSPOT_API_RETRIES",
    default=3,
    description="Number of times to retry a failed hubspot API request",
)
MITOL_HUBSPOT_API_ID_PREFIX = get_string(
    name="MITOL_HUBSPOT_API_ID_PREFIX",
    default="MITXONLINE",
    description="The prefix to use for hubspot unique_app_id field values",
)
HUBSPOT_PIPELINE_ID = get_string(
    name="HUBSPOT_PIPELINE_ID",
    default="default",
    description="Hubspot ID for the ecommerce pipeline",
)
HUBSPOT_MAX_CONCURRENT_TASKS = get_int(
    name="HUBSPOT_MAX_CONCURRENT_TASKS",
    default=4,
    description="Max number of concurrent Hubspot tasks to run",
)
HUBSPOT_TASK_DELAY = get_int(
    name="HUBSPOT_TASK_DELAY",
    default=60,
    description="Number of milliseconds to wait between consecutive Hubspot calls",
)

# PostHog related settings
POSTHOG_PROJECT_API_KEY = get_string(
    name="POSTHOG_PROJECT_API_KEY",
    default="",
    description="API token to communicate with PostHog",
)

POSTHOG_API_HOST = get_string(
    name="POSTHOG_API_HOST",
    default="",
    description="API host for PostHog",
)
POSTHOG_FEATURE_FLAG_REQUEST_TIMEOUT_MS = get_int(
    name="POSTHOG_FEATURE_FLAG_REQUEST_TIMEOUT_MS",
    default=3000,
    description="Timeout(MS) for PostHog feature flag requests.",
)

POSTHOG_MAX_RETRIES = get_int(
    name="POSTHOG_MAX_RETRIES",
    default=3,
    description="Number of times that requests to PostHog should be retried after failing.",
)

POSTHOG_ENABLED = get_bool(
    name="POSTHOG_ENABLED",
    default=False,
    description="Whether PostHog is enabled",
)

# HomePage Hubspot Form Settings
HUBSPOT_HOME_PAGE_FORM_GUID = get_string(
    name="HUBSPOT_HOME_PAGE_FORM_GUID",
    default="",
    description="Hubspot ID for the home page contact form",
)

HUBSPOT_PORTAL_ID = get_string(
    name="HUBSPOT_PORTAL_ID",
    default="",
    description="Hubspot Portal ID",
)

# Unified Ecommerce integration

UNIFIED_ECOMMERCE_URL = get_string(
    name="UNIFIED_ECOMMERCE_URL",
    default="",
    description="The base URL for Unified Ecommerce.",
)

UNIFIED_ECOMMERCE_API_KEY = get_string(
    name="UNIFIED_ECOMMERCE_API_KEY",
    default="",
    description="The API key for Unified Ecommerce.",
)

SPECTACULAR_SETTINGS = open_spectacular_settings


# apigateway configuration

# Disable middleware. For local testing - you can have the middleware in place
# but not use it and use Django's built-in users instead.
MITOL_APIGATEWAY_DISABLE_MIDDLEWARE = get_bool(
    name="MITOL_APIGATEWAY_DISABLE_MIDDLEWARE",
    default=True,
    description="Disable middleware",
)

# Maps user data from the upstream API gateway to the user model(s)
MITOL_APIGATEWAY_USERINFO_MODEL_MAP = {
    # Mappings to the user model.
    "user_fields": {
        # Keys are data returned from the API gateway.
        # Values are tuple of model name (from above) and field name.
        # The base model is "user".
        "preferred_username": "username",
        "email": "email",
        "sub": "global_id",
        "name": ("name", False),
    },
    # Additional models to map in.
    # Key is the model name, then a list of tuples of header field name, model
    # field name, and default. The FK for the related user should be "user".
    "additional_models": {
        # ..then add additional ones here if needed
        "users.UserProfile": [],
        "users.LegalAddress": [],
    },
}

MITOL_APIGATEWAY_USERINFO_ID_SEARCH_FIELD = "global_id"

# Set to True to create users that we see but aren't aware of.
# Set to False if you're managing that elsewhere (like with social-auth).
MITOL_APIGATEWAY_USERINFO_CREATE = get_bool(
    name="MITOL_APIGATEWAY_USERINFO_CREATE",
    default=True,
    description="Create users that we see but aren't aware of",
)

# Set to True to update users we've seen before. If you set this to False, make
# sure there's a backchannel way to update the user data (SCIM, etc) or user
# info will fall out of sync with the IdP pretty quickly.
MITOL_APIGATEWAY_USERINFO_UPDATE = get_bool(
    name="MITOL_APIGATEWAY_USERINFO_UPDATE",
    default=True,
    description="Update users we've seen before",
)

# URL configuation

# Set to the URL that APISIX uses for logout.
MITOL_APIGATEWAY_LOGOUT_URL = "/logout/oidc"

# Set to the default URL the user should be sent to when logging out.
# If there's no redirect URL specified otherwise, the user gets sent here.
MITOL_APIGATEWAY_DEFAULT_POST_LOGOUT_DEST = get_string(
    name="MITOL_APIGATEWAY_DEFAULT_POST_LOGOUT_DEST",
    default="/",
    description="The URL to redirect to after logging out",
)

# Set to the list of hosts the app is allowed to redirect to.
MITOL_APIGATEWAY_ALLOWED_REDIRECT_HOSTS = get_delimited_list(
    name="MITOL_APIGATEWAY_ALLOWED_REDIRECT_HOSTS",
    default=["localhost", "mitxonline.odl.local"],
    description="The list of hosts the app is allowed to redirect to",
)

OPENTELEMETRY_ENABLED = get_bool(
    name="OPENTELEMETRY_ENABLED",
    default=False,
    description="Enable collection and shipment of opentelemetry data",
)
OPENTELEMETRY_SERVICE_NAME = get_string(
    name="OPENTELEMETRY_SERVICE_NAME",
    default="mitxonline",
    description="The name of the service to report to opentelemetry",
)
OPENTELEMETRY_INSECURE = get_bool(
    name="OPENTELEMETRY_INSECURE",
    default=True,
    description="Use insecure connection to opentelemetry",
)
OPENTELEMETRY_ENDPOINT = get_string(
    name="OPENTELEMETRY_ENDPOINT",
    default=None,
    description="Endpoint for opentelemetry",
)
OPENTELEMETRY_TRACES_BATCH_SIZE = get_int(
    name="OPENTELEMETRY_TRACES_BATCH_SIZE",
    default=512,
    description="Batch size for traces",
)
OPENTELEMETRY_EXPORT_TIMEOUT_MS = get_int(
    name="OPENTELEMETRY_EXPORT_TIMEOUT_MS",
    default=5000,
    description="Timeout for opentelemetry export",
)

DISABLE_USER_REPAIR_TASK = get_bool(
    name="DISABLE_USER_REPAIR_TASK",
    default=False,
    description="Disable the task so it no-ops",
)

TRINO_HOST = get_string(
    name="TRINO_HOST",
    default=None,
    description="Host URL for Trino server",
)

TRINO_PORT = get_int(
    name="TRINO_PORT",
    default=443,
    description="Port number for Trino server",
)

TRINO_CATALOG = get_string(
    name="TRINO_CATALOG",
    default=None,
    description="Catalog name for Trino queries",
)

TRINO_USER = get_string(
    name="TRINO_USER",
    default=None,
    description="Username for Trino authentication",
)

TRINO_PASSWORD = get_string(
    name="TRINO_PASSWORD",
    default=None,
    description="Password for Trino authentication",
)
