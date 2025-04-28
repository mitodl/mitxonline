"""User utils tests"""

import random
from datetime import datetime
from email.utils import parseaddr
from unittest.mock import patch

import pytest
import pytz
from django.conf import settings

from users.factories import UserFactory
from users.utils import (
    determine_approx_age,
    ensure_active_user,
    format_recipient,
    is_duplicate_username_error,
    usernameify,
)


@pytest.mark.parametrize(
    "full_name,email,expected_username",  # noqa: PT006
    [
        [" John  Doe ", None, "john-doe"],  # noqa: PT007
        ["Tabby	Tabberson", None, "tabby-tabberson"],  # noqa: PT007
        ["Àccèntèd Ñame, Ësq.", None, "àccèntèd-ñame-ësq"],  # noqa: PT007
        ["-Dashy_St._Underscores-", None, "dashy-st-underscores"],  # noqa: PT007
        ["Repeated-----Chars___Jr.", None, "repeated-chars-jr"],  # noqa: PT007
        ["Numbers123 !$!@ McStrange!!##^", None, "numbers-mcstrange"],  # noqa: PT007
        ["Кирил Френков", None, "кирил-френков"],  # noqa: PT007
        ["年號", None, "年號"],  # noqa: PT007
        ["abcdefghijklmnopqrstuvwxyz", None, "abcdefghijklmnopqrst"],  # noqa: PT007
        ["ai bi cı dI eİ fI", None, "ai-bi-ci-di-ei-fi"],  # noqa: PT007, RUF001
        ["", "some.email@example.co.uk", "someemail"],  # noqa: PT007
    ],
)
def test_usernameify(mocker, full_name, email, expected_username):
    """Usernameify should turn a user's name into a username, or use the email if necessary"""
    # Change the username max length to 20 for test data simplicity's sake
    temp_username_max_len = 20
    mocker.patch("users.utils.USERNAME_MAX_LEN", temp_username_max_len)
    patched_log_error = mocker.patch("users.utils.log.error")

    assert usernameify(full_name, email=email) == expected_username
    assert patched_log_error.called == bool(email and not full_name)


def test_usernameify_fail():
    """Usernameify should raise an exception if the full name and email both fail to produce a username"""
    with pytest.raises(ValueError):  # noqa: PT011
        assert usernameify("!!!", email="???@example.com")


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


@pytest.mark.django_db
@patch("openedx.api.repair_faulty_edx_user", return_value=(None, None))
def test_ensure_active_user(mock_repair_faulty_edx_user):
    """
    Test that ensure_active_user activates and tries to repair openedx user record
    """
    user = UserFactory.create(no_openedx_user=True)
    user.is_active = False
    user.save()

    assert not user.is_active

    ensure_active_user(user)
    mock_repair_faulty_edx_user.assert_called_once_with(user)
    assert user.is_active


def test_format_recipient(user):
    """Verify that format_recipient correctly format's a user's name and email"""
    name, email = parseaddr(format_recipient(user))
    assert name == user.name
    assert email == user.email


def test_determine_approx_age():
    """Verify that determine_approx_age works correctly"""

    now = datetime.now(tz=pytz.timezone(settings.TIME_ZONE))
    test_year = now.year - random.randrange(0, 50)  # noqa: S311
    test_age = now.year - test_year

    assert determine_approx_age(test_year) == test_age
