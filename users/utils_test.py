"""User utils tests"""

import random
from datetime import datetime
from email.utils import parseaddr
from zoneinfo import ZoneInfo

import pytest
from django.conf import settings

from users.utils import (
    determine_approx_age,
    format_recipient,
    is_duplicate_username_error,
)


@pytest.mark.parametrize(
    "exception_text,expected_value",  # noqa: PT006
    [
        ["DETAILS: (username)=(ABCDEFG) already exists", True],  # noqa: PT007
        ["DETAILS: (email)=(ABCDEFG) already exists", False],  # noqa: PT007
    ],
)
def test_is_duplicate_username_error(exception_text, expected_value):
    """
    is_duplicate_username_error should return True if the exception text provided indicates a duplicate username error
    """
    assert is_duplicate_username_error(exception_text) is expected_value


def test_format_recipient(user):
    """Verify that format_recipient correctly format's a user's name and email"""
    name, email = parseaddr(format_recipient(user))
    assert name == user.name
    assert email == user.email


def test_determine_approx_age():
    """Verify that determine_approx_age works correctly"""

    now = datetime.now(tz=ZoneInfo(settings.TIME_ZONE))
    test_year = now.year - random.randrange(0, 50)  # noqa: S311
    test_age = now.year - test_year

    assert determine_approx_age(test_year) == test_age
