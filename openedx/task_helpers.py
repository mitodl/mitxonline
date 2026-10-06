"""Helpers for queueing Open edX sync tasks from request-handling code."""

import logging

from openedx import tasks
from users.models import User

log = logging.getLogger(__name__)


def queue_edx_user_profile_update(user: User) -> None:
    """
    Trigger the celery task that pushes a user's profile to Open edX.

    Never raises: callers run inside request handling (notably the SCIM API),
    which must not fail because the broker is unavailable.

    Args:
        user (User): the user whose profile should be pushed to Open edX
    """
    try:
        tasks.update_edx_user_profile.delay(user.id)
    except Exception:
        log.exception("Failed to queue edX profile update for user %s", user.id)


def queue_edx_user_email_change(user: User) -> None:
    """
    Trigger the celery task that pushes a user's email change to Open edX.

    Never raises, for the same reason as queue_edx_user_profile_update.

    Args:
        user (User): the user whose email should be pushed to Open edX
    """
    try:
        tasks.change_edx_user_email_async.delay(user.id)
    except Exception:
        log.exception("Failed to queue edX email update for user %s", user.id)
