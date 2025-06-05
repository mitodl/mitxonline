"""User app utility functions"""

import logging
import re
from datetime import datetime
from email.utils import formataddr

import pytz
from django.conf import settings
from django.contrib.auth import get_user_model

User = get_user_model()
log = logging.getLogger(__name__)


def is_duplicate_username_error(exc):
    """
    Returns True if the given exception indicates that there was an attempt to save a User record with an
    already-existing username.

    Args:
        exc (Exception): An exception

    Returns:
        bool: Whether or not the exception indicates a duplicate username error
    """
    return re.search(r"\(username\)=\([^\s]+\) already exists", str(exc)) is not None


def format_recipient(user: User) -> str:
    """Format the user as a recipient"""
    return formataddr((user.name, user.email))


def determine_approx_age(year: int):
    """Determines the approximage age based on the year"""

    return datetime.now(tz=pytz.timezone(settings.TIME_ZONE)).year - year
