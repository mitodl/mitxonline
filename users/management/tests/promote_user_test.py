"""Tests for the promote_user command"""

from io import StringIO

import faker
import pytest
from django.core.management import CommandError, call_command

pytestmark = pytest.mark.django_db
FAKE = faker.Faker()


def test_promote_user_bad_args(user):
    """Test that the command raises an error with bad arguments."""
    out = StringIO()

    with pytest.raises(CommandError) as exc:
        call_command(
            "promote_user",
            "--promote",
            "--demote",
            user.email,
            stdout=out,
        )

    assert "You cannot provide both --promote and --demote." in str(exc.value)

    with pytest.raises(CommandError) as exc:
        call_command(
            "promote_user",
            "--promote",
            FAKE.email(),
            stdout=out,
        )

    assert "User with email" in str(exc.value)

    with pytest.raises(CommandError) as exc:
        call_command(
            "promote_user",
            "--superuser",
            user.email,
            stdout=out,
        )

    assert "You must provide either --promote or --demote" in str(exc.value)


@pytest.mark.parametrize("to_superuser", [True, False])
def test_promote_user(user, to_superuser):
    """Test that promote_user promotes the user correctly."""
    out = StringIO()

    if to_superuser:
        call_command(
            "promote_user",
            "--promote",
            "--superuser",
            user.email,
            stdout=out,
        )
    else:
        call_command(
            "promote_user",
            "--promote",
            user.email,
            stdout=out,
        )

    user.refresh_from_db()

    assert "promoted" in out.getvalue()

    if to_superuser:
        assert "to superuser" in out.getvalue()
    else:
        assert "to superuser" not in out.getvalue()

    assert user.is_superuser == to_superuser
    assert user.is_staff


@pytest.mark.parametrize("from_superuser", [True, False])
def test_demote_user(user, from_superuser):
    """Test that promote_user demotes the user correctly."""
    out = StringIO()

    if from_superuser:
        user.is_superuser = True
        user.is_staff = True
        user.save()

        call_command(
            "promote_user",
            "--demote",
            "--superuser",
            user.email,
            stdout=out,
        )
    else:
        user.is_staff = True
        user.save()

        call_command(
            "promote_user",
            "--demote",
            user.email,
            stdout=out,
        )

    user.refresh_from_db()

    assert "demoted" in out.getvalue()

    if from_superuser:
        assert "to staff" in out.getvalue()
        assert not user.is_superuser
        assert user.is_staff
    else:
        assert not user.is_superuser
        assert not user.is_staff
