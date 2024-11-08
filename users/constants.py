"""User constants"""

import re

USERNAME_MAX_LEN = 30

US_POSTAL_RE = re.compile(r"[0-9]{5}(-[0-9]{4}){0,1}")
CA_POSTAL_RE = re.compile(r"[A-Z]\d[A-Z] \d[A-Z]\d$", flags=re.I)
USER_GIVEN_NAME_RE = re.compile(
    r"""
    ^                               # Start of string
    (?![~!@&)(+:'.?/,`-]+)          # String should not start from character(s) in this set - They can exist in elsewhere
    ([^/^$#*=\[\]`%_;<>{}\"|]+)     # String should not contain characters(s) from this set - All invalid characters
    $                               # End of string
    """,
    flags=re.I | re.VERBOSE | re.MULTILINE,
)
USERNAME_RE_PARTIAL = r"[\w ._+-]+"
USERNAME_RE = re.compile(rf"(?P<username>{USERNAME_RE_PARTIAL})")
USERNAME_ERROR_MSG = "Username can only contain letters, numbers, spaces, and the following characters: _+-"
USERNAME_ALREADY_EXISTS_MSG = (
    "A user already exists with this username. Please try a different one."
)
EMAIL_CONFLICT_MSG = (
    "This email is associated with an existing account. Please try a different one."
)

OPENEDX_ACCOUNT_CREATION_VALIDATION_MSGS_MAP = {
    "It looks like this username is already taken": USERNAME_ALREADY_EXISTS_MSG,
    "This email is already associated with an existing account": EMAIL_CONFLICT_MSG,
}

EMAIL_ERROR_MSG = "Email address already exists in the system."
