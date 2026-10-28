"""Tests for the 0045_username_from_email data migration"""

from importlib import import_module

import pytest
from django.apps import apps

from users.factories import UserFactory

pytestmark = pytest.mark.django_db

migration = import_module("users.migrations.0045_username_from_email")


def _run_and_get_usernames(*users):
    migration.username_from_email(apps, None)
    for user in users:
        user.refresh_from_db()
    return [user.username for user in users]


@pytest.mark.parametrize(
    "username",
    ["jdoe", "John.Doe@example.com"],
)
def test_username_from_email_sets_lowercased_email(username):
    """A handle, or the email in another case, becomes the lowercased email"""
    user = UserFactory.create(username=username, email="John.Doe@example.com")

    assert _run_and_get_usernames(user) == ["john.doe@example.com"]


def test_username_from_email_skips_blank_email():
    """A user with no email keeps their username"""
    user = UserFactory.create(username="jdoe", email="")

    assert _run_and_get_usernames(user) == ["jdoe"]


@pytest.mark.parametrize("taken", ["taken@example.com", "TAKEN@example.com"])
def test_username_from_email_skips_email_taken_as_username(taken):
    """A user whose email is another user's username keeps their username"""
    user = UserFactory.create(username="jdoe", email="taken@example.com")
    # a blank email keeps the other user's username where it is
    other = UserFactory.create(username=taken, email="")

    assert _run_and_get_usernames(user, other) == ["jdoe", taken]


def test_username_from_email_follows_a_chain():
    """A user blocked by another user's old username is updated once it moves"""
    first = UserFactory.create(username="jdoe", email="next@example.com")
    second = UserFactory.create(username="next@example.com", email="last@example.com")

    assert _run_and_get_usernames(first, second) == [
        "next@example.com",
        "last@example.com",
    ]
