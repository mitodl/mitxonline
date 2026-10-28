"""Tests for the 0045_username_from_email data migration"""

from importlib import import_module

import pytest
from django.apps import apps

from users.factories import UserFactory
from users.models import User

pytestmark = pytest.mark.django_db

migration = import_module("users.migrations.0045_username_from_email")


def test_username_from_email_sets_handle_to_email():
    """A user with a handle for a username gets their email instead"""
    user = UserFactory.create(username="jdoe", email="John.Doe@example.com")

    migration.username_from_email(apps, None)

    user.refresh_from_db()
    assert user.username == "John.Doe@example.com"


def test_username_from_email_leaves_case_only_difference():
    """A username that is the email in another case is left as it is"""
    user = UserFactory.create(
        username="john.doe@example.com", email="John.Doe@example.com"
    )

    migration.username_from_email(apps, None)

    user.refresh_from_db()
    assert user.username == "john.doe@example.com"


def test_username_from_email_skips_email_taken_as_username():
    """A user whose email is another user's username keeps their username"""
    user = UserFactory.create(username="jdoe", email="taken@example.com")
    UserFactory.create(username="TAKEN@example.com", email="other@example.com")

    migration.username_from_email(apps, None)

    user.refresh_from_db()
    assert user.username == "jdoe"
    assert User.objects.filter(username="other@example.com").exists()
