# pylint: disable=too-many-lines
"""
Django settings for main.
"""
import logging
import os
import platform
from datetime import timedelta
from urllib.parse import urljoin, urlparse

import dj_database_url
from celery.schedules import crontab
from django.core.exceptions import ImproperlyConfigured
from mitol.common.envs import (
    get_bool,
    get_delimited_list,
    get_features,
    get_int,
    get_string,
    import_settings_modules,
)

from mitol.payment_gateway.constants import MITOL_PAYMENT_GATEWAY_CYBERSOURCE
from mitol.google_sheets.settings.google_sheets import *
from mitol.google_sheets_refunds.settings.google_sheets_refunds import *

from redbeat import RedBeatScheduler

from main.celery_utils import OffsettingSchedule
from main.sentry import init_sentry

VERSION = "0.45.7"

log = logging.getLogger()

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
init_sentry(
    dsn=SENTRY_DSN,
    environment=ENVIRONMENT,
    version=VERSION,
    send_default_pii=True,
    log_level=SENTRY_LOG_LEVEL,
    heroku_app_name=HEROKU_APP_NAME,
)

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SITE_BASE_URL = get_string(
    name="MITX_ONLINE_BASE_URL",
    default=None,
    description="Base url for the application in the format PROTOCOL://HOSTNAME[:PORT]",
    required=True,
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

SECURE_SSL_REDIRECT = get_bool(
    name="MITX_ONLINE_SECURE_SSL_REDIRECT",
    default=True,
    description="Application-level SSL redirect setting.",
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
        "STATS_FILE": os.path.join(BASE_DIR, "webpack-stats/default.json"),
        "POLL_INTERVAL": 0.1,
        "TIMEOUT": None,
        "IGNORE": [r".+\.hot-update\.+", r".+\.js\.map"],
    },
    "STAFF_DASHBOARD": {
        "CACHE": not DEBUG,
        "STATS_FILE": os.path.join(BASE_DIR, "webpack-stats/staff-dashboard.json"),
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
    "server_status",
    "oauth2_provider",
    "rest_framework",
    "anymail",
    "django_filters",
    "corsheaders",
    "webpack_loader",
    # WAGTAIL
    "wagtail.contrib.forms",
    "wagtail.contrib.redirects",
    "wagtail.contrib.postgres_search",
    "wagtail.embeds",
    "wagtail.sites",
    "wagtail.users",
    "wagtail.snippets",
    "wagtail.documents",
    "wagtail.images",
    "wagtail.search",
    "wagtail.admin",
    "wagtail.core",
    "modelcluster",
    "taggit",
    # django-fsm-admin
    "django_fsm",
    "fsm_admin",
    # django-robots
    "robots",
    # django-reversion
    "reversion",
    # Put our apps after this point
    "main",
    "authentication",
    "courses",
    "mail.apps.MailApp",
    "users",
    "cms",
    "sheets",
    # "compliance",
    "openedx",
    # must be after "users" to pick up custom user model
    "compat",
    "hijack",
    "hijack_admin",
    "ecommerce",
    "flexiblepricing",
    "micromasters_import",
    # ol-dango apps, must be after this project's apps for template precedence
    "mitol.common.apps.CommonApp",
    "mitol.google_sheets.apps.GoogleSheetsApp",
    "mitol.google_sheets_refunds.apps.GoogleSheetsRefundsApp",
    # "mitol.digitalcredentials.apps.DigitalCredentialsApp",
    "mitol.mail.apps.MailApp",
    "mitol.authentication.apps.TransitionalAuthenticationApp",
    "mitol.payment_gateway.apps.PaymentGatewayApp"
    # "mitol.oauth_toolkit_extensions.apps.OAuthToolkitExtensionsApp",
)
# Only include the seed data app if this isn't running in prod
# if ENVIRONMENT not in ("production", "prod"):
#     INSTALLED_APPS += ("localdev.seed",)

MIDDLEWARE = (
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "oauth2_provider.middleware.OAuth2TokenMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.contrib.sites.middleware.CurrentSiteMiddleware",
    "django_user_agents.middleware.UserAgentMiddleware",
    "main.middleware.CachelessAPIMiddleware",
    "wagtail.contrib.redirects.middleware.RedirectMiddleware",
)

# enable the nplusone profiler only in debug mode
if DEBUG:
    INSTALLED_APPS += ("nplusone.ext.django",)
    MIDDLEWARE += ("nplusone.ext.django.NPlusOneMiddleware",)

SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"

LOGIN_REDIRECT_URL = "/"
LOGIN_URL = "/signin"
LOGIN_ERROR_URL = "/signin"
LOGOUT_REDIRECT_URL = get_string(
    name="LOGOUT_REDIRECT_URL",
    default="/",
    description="Url to redirect to after logout, typically Open edX's own logout url",
)

ROOT_URLCONF = "main.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
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
        default="sqlite:///{0}".format(os.path.join(BASE_DIR, "db.sqlite3")),
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

USE_L10N = True

USE_TZ = True

# django-robots
ROBOTS_USE_HOST = False
ROBOTS_CACHE_TIMEOUT = get_int(
    name="ROBOTS_CACHE_TIMEOUT",
    default=60 * 60 * 24,
    description="How long the robots.txt file should be cached",
)

SOCIAL_AUTH_LOGIN_ERROR_URL = "login"
SOCIAL_AUTH_ALLOWED_REDIRECT_HOSTS = [urlparse(SITE_BASE_URL).netloc]

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
    # verify the user against export compliance
    # "authentication.pipeline.compliance.verify_exports_compliance",
    # Create the record that associates the social account with the user.
    "social_core.pipeline.social_auth.associate_user",
    # activate the user
    "authentication.pipeline.user.activate_user",
    # create the user's edx user and auth
    "authentication.pipeline.user.create_openedx_user",
    # Populate the extra_data field in the social record with the values
    # specified by settings (and the default ones like access_token, etc).
    "social_core.pipeline.social_auth.load_extra_data",
    # Update the user record with any changed info from the auth service.
    "social_core.pipeline.user.user_details",
)

AUTH_CHANGE_EMAIL_TTL_IN_MINUTES = get_int(
    name="AUTH_CHANGE_EMAIL_TTL_IN_MINUTES",
    default=60 * 24,
    description="Expiry time for a change email request, default is 1440 minutes(1 day)",
)

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
    STATIC_URL = urljoin(
        "https://{dist}.cloudfront.net".format(dist=CLOUDFRONT_DIST), STATIC_URL
    )

STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]

STATIC_ROOT = "staticfiles"
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "static"),
]
for name, path in [
    ("mitx-online", os.path.join(BASE_DIR, "frontend/public/build")),
    ("staff-dashboard", os.path.join(BASE_DIR, "frontend/staff-dashboard/build")),
]:
    if os.path.exists(path):
        STATICFILES_DIRS.append((name, path))
    else:
        log.warn(f"Static file directory was missing: {path}")

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

MITX_ONLINE_REPLY_TO_ADDRESS = get_string(
    name="MITX_ONLINE_REPLY_TO_ADDRESS",
    default="webmaster@localhost",
    description="E-mail to use for reply-to address of emails",
)

DEFAULT_FROM_EMAIL = get_string(
    name="MITX_ONLINE_FROM_EMAIL",
    default="webmaster@localhost",
    description="E-mail to use for the from field",
)

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
MAILGUN_FROM_EMAIL = get_string(
    name="MAILGUN_FROM_EMAIL",
    default="no-reply@localhost",
    description="Email which mail comes from",
)

EMAIL_SUPPORT = get_string(
    name="MITX_ONLINE_SUPPORT_EMAIL",
    default=MAILGUN_RECIPIENT_OVERRIDE or "support@localhost",
    description="Email address listed for customer support",
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
if ADMIN_EMAIL != "":
    ADMINS = (("Admins", ADMIN_EMAIL),)
else:
    ADMINS = ()

# Logging configuration
LOG_LEVEL = get_string(
    name="MITX_ONLINE_LOG_LEVEL", default="INFO", description="The log level default"
)
DJANGO_LOG_LEVEL = get_string(
    name="DJANGO_LOG_LEVEL", default="INFO", description="The log level for django"
)

# For logging to a remote syslog host
LOG_HOST = get_string(
    name="MITX_ONLINE_LOG_HOST",
    default="localhost",
    description="Remote syslog server hostname",
)
LOG_HOST_PORT = get_int(
    name="MITX_ONLINE_LOG_HOST_PORT",
    default=514,
    description="Remote syslog server port",
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
                "[{hostname}] - %(message)s"
            ).format(hostname=HOSTNAME),
            "datefmt": "%Y-%m-%d %H:%M:%S",
        }
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "syslog": {
            "level": LOG_LEVEL,
            "class": "logging.handlers.SysLogHandler",
            "facility": "local7",
            "formatter": "verbose",
            "address": (LOG_HOST, LOG_HOST_PORT),
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
            "handlers": ["console", "syslog"],
        },
        "django.request": {
            "handlers": ["mail_admins"],
            "level": DJANGO_LOG_LEVEL,
            "propagate": True,
        },
        "nplusone": {"handlers": ["console"], "level": "ERROR"},
    },
    "root": {"handlers": ["console", "syslog"], "level": LOG_LEVEL},
}

# server-status
STATUS_TOKEN = get_string(
    name="STATUS_TOKEN", default="", description="Token to access the status API."
)
HEALTH_CHECK = ["CELERY", "REDIS", "POSTGRES"]

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
    default="mitX Online",
    description="Name of the site. e.g MIT mitX Online",
)
WAGTAIL_SITE_NAME = SITE_NAME

WAGTAILSEARCH_BACKENDS = {
    "default": {
        "BACKEND": "wagtail.contrib.postgres_search.backend",
        "ATOMIC_REBUILD": True,
    },
}

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
        "You have enabled S3 support, but are missing one of "
        "AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, or "
        "AWS_STORAGE_BUCKET_NAME"
    )
if MITX_ONLINE_USE_S3:
    if CLOUDFRONT_DIST:
        AWS_S3_CUSTOM_DOMAIN = "{dist}.cloudfront.net".format(dist=CLOUDFRONT_DIST)
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
    default=0,
    description="'hours' value for the 'generate-course-certificate' scheduled task (defaults to midnight)",
)
CRON_COURSE_CERTIFICATES_DAYS = get_string(
    name="CRON_COURSE_CERTIFICATES_DAYS",
    default="*",
    description="'day_of_week' value for 'generate-course-certificate' scheduled task (default will run once a day).",
)
CERTIFICATE_CREATION_DELAY_IN_HOURS = get_int(
    name="CERTIFICATE_CREATION_DELAY_IN_HOURS",
    default=24,
    description="The number of hours to delay automated certificate creation after a course run ends.",
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
    "process-refund-requests": {
        "task": "sheets.tasks.process_refund_requests",
        "schedule": crontab(minute=CRON_PROCESS_REFUND_REQUESTS_MINUTES),
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
}

AUTHENTICATION_BACKENDS = (
    "social_core.backends.email.EmailAuth",
    "oauth2_provider.backends.OAuth2Backend",
    "django.contrib.auth.backends.ModelBackend",
)


# required for migrations
OAUTH2_PROVIDER_ACCESS_TOKEN_MODEL = "oauth2_provider.AccessToken"
OAUTH2_PROVIDER_APPLICATION_MODEL = "oauth2_provider.Application"
OAUTH2_PROVIDER_REFRESH_TOKEN_MODEL = "oauth2_provider.RefreshToken"

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
        # "digitalcredentials": "Can read and write Digital Credentials data",
    },
    "DEFAULT_SCOPES": ["user:read"],
    "OAUTH2_VALIDATOR_CLASS": "main.oidc_provider_settings.CustomOAuth2Validator",
    # "SCOPES_BACKEND_CLASS": "mitol.oauth_toolkit_extensions.backends.ApplicationAccessOrSettingsScopes",
    "ERROR_RESPONSE_WITH_SCOPES": DEBUG,
    "ALLOWED_REDIRECT_URI_SCHEMES": get_delimited_list(
        name="OAUTH2_PROVIDER_ALLOWED_REDIRECT_URI_SCHEMES",
        default=["http", "https"],
        description="List of schemes allowed for oauth2 redirect URIs",
    ),
}


# DRF configuration
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.SessionAuthentication",
        "oauth2_provider.contrib.rest_framework.OAuth2Authentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "EXCEPTION_HANDLER": "main.exceptions.exception_handler",
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}

# Relative URL to be used by Djoser for the link in the password reset email
# (see: http://djoser.readthedocs.io/en/stable/settings.html#password-reset-confirm-url)
PASSWORD_RESET_CONFIRM_URL = "password_reset/confirm/{uid}/{token}/"

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

MITX_ONLINE_OAUTH_PROVIDER = "mitxpro-oauth2"
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
OPENEDX_API_KEY = get_string(
    name="OPENEDX_API_KEY",
    default=None,
    description="edX API key (EDX_API_KEY setting in Open edX)",
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
EDX_API_CLIENT_TIMEOUT = get_int(
    name="EDX_API_CLIENT_TIMEOUT",
    default=60,
    description="Timeout (in seconds) for requests made via the edX API client",
)

# django debug toolbar only in debug mode
if DEBUG:
    INSTALLED_APPS += ("debug_toolbar",)
    # it needs to be enabled before other middlewares
    MIDDLEWARE = ("debug_toolbar.middleware.DebugToolbarMiddleware",) + MIDDLEWARE

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

MITOL_GOOGLE_SHEETS_REFUNDS_PLUGINS = ["sheets.plugins.RefundPlugin"]


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
