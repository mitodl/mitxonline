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

USERNAME_SEPARATOR = "-"
# Characters that should be replaced by the specified separator character
USERNAME_SEPARATOR_REPLACE_CHARS = "\\s_"
# Characters that should be removed entirely from the full name to create the username
USERNAME_INVALID_CHAR_PATTERN = (
    rf"[^\w{USERNAME_SEPARATOR_REPLACE_CHARS}{USERNAME_SEPARATOR}]|[\d]"
)

USERNAME_TURKISH_I_CHARS = r"[ıİ]"
USERNAME_TURKISH_I_CHARS_REPLACEMENT = "i"

# Pattern for chars to replace with a single separator. The separator character itself
# is also included in this pattern so repeated separators are squashed down.
USERNAME_SEPARATOR_REPLACE_PATTERN = (
    rf"[{USERNAME_SEPARATOR_REPLACE_CHARS}{USERNAME_SEPARATOR}]+"
)


def _reformat_for_username(string):
    """
    Removes/substitutes characters in a string to make it suitable as a username value

    Args:
        string (str): A string
    Returns:
        str: A version of the string with username-appropriate characters
    """
    cleaned_string = re.sub(USERNAME_INVALID_CHAR_PATTERN, "", string)
    cleaned_string = re.sub(
        USERNAME_TURKISH_I_CHARS, USERNAME_TURKISH_I_CHARS_REPLACEMENT, cleaned_string
    )
    return (
        re.sub(USERNAME_SEPARATOR_REPLACE_PATTERN, USERNAME_SEPARATOR, cleaned_string)
        .lower()
        .strip(USERNAME_SEPARATOR)
    )


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
