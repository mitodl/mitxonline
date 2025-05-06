"""Tests for the migrate_usernames command"""

from io import StringIO
from unittest import mock

import faker
import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from users.constants import USERNAME_MAX_LEN
from users.factories import UserFactory

pytestmark = pytest.mark.django_db
FAKE = faker.Faker()
User = get_user_model()


@pytest.mark.parametrize("break_one", [False, True])
def test_migrate_usernames(break_one):
    """Test that the migrate_usernames command works correctly with good data."""
    out = StringIO()

    # UserFactory uses fuzzytext, so just create a batch of them and run
    # through it.
    UserFactory.create_batch(10)

    if break_one:
        # Force a username collision - set a user's username to the same as
        # another user's email address.
        random_idx = FAKE.random_int(0, 7)
        user1 = User.objects.all()[random_idx]
        user2 = User.objects.all()[random_idx + 1]
        user2.username = user1.email[:USERNAME_MAX_LEN]
        user2.save()

    with mock.patch(
        "users.management.commands.migrate_usernames.MIGRATE_USERNAME_BATCH_SIZE", 3
    ):
        call_command(
            "migrate_usernames",
            stdout=out,
        )

        if break_one:
            assert "Skipping update" in out.getvalue()
            user1.refresh_from_db()
            assert user1.username != user1.email[:USERNAME_MAX_LEN]
        else:
            assert "Successfully updated 10" in out.getvalue()

        for user in User.objects.all():
            if not user1 or user.id != user1.id:
                assert user.username == user.email[:USERNAME_MAX_LEN]
