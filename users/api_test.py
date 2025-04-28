"""Tests for user api"""

import factory
import pytest
from django.contrib.auth import get_user_model

from users.api import fetch_user, fetch_users, find_available_username, get_user_by_id
from users.factories import UserFactory

User = get_user_model()


def test_get_user_by_id(user):
    """Tests get_user_by_id"""
    assert get_user_by_id(user.id) == user


@pytest.mark.django_db
@pytest.mark.parametrize(
    "prop,value,db_value",  # noqa: PT006
    [
        ["username", "abcdefgh", None],  # noqa: PT007
        ["id", 100, None],  # noqa: PT007
        ["id", "100", 100],  # noqa: PT007
        ["email", "abc@example.com", None],  # noqa: PT007
    ],
)
def test_fetch_user(prop, value, db_value):
    """
    fetch_user should return a User that matches a provided value which represents
    an id, email, or username
    """
    user = UserFactory.create(**{prop: db_value or value})
    found_user = fetch_user(value)
    assert user == found_user


@pytest.mark.django_db
def test_fetch_user_case_sens():
    """fetch_user should be able to fetch a User with a case-insensitive filter"""
    email = "abc@example.com"
    user = UserFactory.create(email=email)
    upper_email = email.upper()
    with pytest.raises(User.DoesNotExist):
        fetch_user(upper_email, ignore_case=False)
    assert fetch_user(upper_email, ignore_case=True) == user


@pytest.mark.django_db
def test_fetch_user_fail():
    """fetch_user should raise an exception if a matching User was not found"""
    with pytest.raises(User.DoesNotExist):
        fetch_user("missingemail@example.com")


@pytest.mark.django_db
@pytest.mark.parametrize(
    "prop,values,db_values",  # noqa: PT006
    [
        ["username", ["abcdefgh", "ijklmnop", "qrstuvwxyz"], None],  # noqa: PT007
        ["id", [100, 101, 102], None],  # noqa: PT007
        ["id", ["100", "101", "102"], [100, 101, 102]],  # noqa: PT007
        ["email", ["abc@example.com", "def@example.com", "ghi@example.com"], None],  # noqa: PT007
    ],
)
def test_fetch_users(prop, values, db_values):
    """
    fetch_users should return a set of Users that match some provided values which represent
    ids, emails, or usernames
    """
    users = UserFactory.create_batch(
        len(values), **{prop: factory.Iterator(db_values or values)}
    )
    found_users = fetch_users(values)
    assert set(users) == set(found_users)


@pytest.mark.django_db
def test_fetch_users_case_sens():
    """fetch_users should be able to fetch Users with a case-insensitive filter"""
    emails = ["abc@example.com", "def@example.com", "ghi@example.com"]
    users = UserFactory.create_batch(len(emails), email=factory.Iterator(emails))
    upper_emails = list(map(str.upper, emails))
    with pytest.raises(User.DoesNotExist):
        fetch_users(upper_emails, ignore_case=False)
    assert set(fetch_users(upper_emails, ignore_case=True)) == set(users)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "prop,existing_values,missing_values",  # noqa: PT006
    [
        ["username", ["abcdefgh"], ["ijklmnop", "qrstuvwxyz"]],  # noqa: PT007
        ["id", [100], [101, 102]],  # noqa: PT007
        ["email", ["abc@example.com"], ["def@example.com", "ghi@example.com"]],  # noqa: PT007
    ],
)
def test_fetch_users_fail(prop, existing_values, missing_values):
    """
    fetch_users should raise an exception if any provided values did not match a User, and
    the exception message should contain info about the values that did not match.
    """
    fetch_users_values = existing_values + missing_values
    UserFactory.create_batch(
        len(existing_values), **{prop: factory.Iterator(existing_values)}
    )
    expected_missing_value_output = str(sorted(list(missing_values)))  # noqa: C414
    with pytest.raises(User.DoesNotExist, match=expected_missing_value_output):
        fetch_users(fetch_users_values)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "username_base,suffixed_to_create,expected_available_username",  # noqa: PT006
    [
        ["someuser", 0, "someuser1"],  # noqa: PT007
        ["someuser", 5, "someuser6"],  # noqa: PT007
        ["abcdefghij", 10, "abcdefgh11"],  # noqa: PT007
        ["abcdefghi", 99, "abcdefg100"],  # noqa: PT007
    ],
)
def test_find_available_username(
    mocker, username_base, suffixed_to_create, expected_available_username
):
    """find_available_username should return an available username with the lowest possible suffix"""
    # Change the username max length to 10 for test data simplicity's sake
    temp_username_max_len = 10
    mocker.patch("users.api.USERNAME_MAX_LEN", temp_username_max_len)

    def suffixed_username_generator():
        """Generator for usernames with suffixes that will not exceed the username character limit"""
        for suffix_int in range(1, suffixed_to_create + 1):
            suffix = str(suffix_int)
            username = f"{username_base}{suffix}"
            if len(username) <= temp_username_max_len:
                yield username
            else:
                num_extra_characters = len(username) - temp_username_max_len
                yield f"{username_base[0 : len(username_base) - num_extra_characters]}{suffix}"

    UserFactory.create(username=username_base)
    UserFactory.create_batch(
        suffixed_to_create, username=factory.Iterator(suffixed_username_generator())
    )
    available_username = find_available_username(username_base)
    assert available_username == expected_available_username
