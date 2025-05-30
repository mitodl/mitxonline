"""Sentry setup and configuration"""

import logging

import sentry_sdk
from celery.exceptions import WorkerLostError
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.redis import RedisIntegration

# these errors occur when a shutdown is happening (usually caused by a SIGTERM)
SHUTDOWN_ERRORS = (WorkerLostError, SystemExit)

log = logging.getLogger()


def before_send(event, hint):
    """
    Filter or transform events before they're sent to Sentry

    Args:
        event (dict): event object
        hint (dict): event hints, see https://docs.sentry.io/platforms/python/#hints

    Returns:
        dict or None: returns the modified event or None to filter out the event
    """
    if "exc_info" in hint:
        _, exc_value, _ = hint["exc_info"]
        if isinstance(exc_value, SHUTDOWN_ERRORS):
            # so we don't want to report expected shutdown errors to sentry
            return None
    return event


def init_sentry(  # noqa: PLR0913
    *, dsn, environment, version, send_default_pii, log_level, heroku_app_name, traces_sample_rate, profiles_sample_rate
):
    """
    Initializes sentry

    Args:
        dsn (str): the sentry DSN key
        environment (str): the application environment
        version (str): the version of the application
        send_default_pii (bool): enable sending PII data to associate users to errors
        log_level (str): the sentry log level
        heroku_app_name (str or None): the name of the heroku review app
        traces_sample_rate (int): int between 0 and 100 for the sample rate
        profiles_sample_rate (int): int between 0 and 100 for the sample rate
    """
    if not 0 <= traces_sample_rate <= 1:
        log.error(
            "SENTRY_TRACES_SAMPLE_RATE should be between 0 <= x <= 1, defaulting to 0"
        )
        traces_sample_rate = 0

    if not 0 <= profiles_sample_rate <= 1:
        log.error(
            "SENTRY_PROFILES_SAMPLE_RATE should be between 0 <= x <= 1, defaulting to 0"
        )
        profiles_sample_rate = 0
    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=version,
        before_send=before_send,
        send_default_pii=send_default_pii,
        traces_sample_rate=traces_sample_rate,
        profiles_sample_rate=profiles_sample_rate,
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),
            RedisIntegration(),
            LoggingIntegration(level=log_level),
        ],
    )

    with sentry_sdk.configure_scope() as scope:
        if heroku_app_name:
            scope.set_tag("review_app_name", heroku_app_name)
