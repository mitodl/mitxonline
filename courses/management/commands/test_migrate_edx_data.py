"""Tests for migrate_edx_data management command's user-migration bulk_create fix"""

import pytest

from courses.management.commands.migrate_edx_data import Command
from users.factories import UserFactory
from users.models import LegalAddress, User, UserProfile

pytestmark = pytest.mark.django_db


class FakeCursor:
    """Minimal stand-in for a Trino DB-API cursor."""

    def __init__(self, columns, rows):
        self.description = [(col,) for col in columns]
        self._rows = rows
        self._offset = 0

    def execute(self, query):
        """No-op - the fake cursor already has its rows in memory."""

    def fetchmany(self, size):
        """Return the next slice of rows, matching the DB-API contract."""
        batch = self._rows[self._offset : self._offset + size]
        self._offset += size
        return batch


class FakeConnection:
    """Minimal stand-in for a Trino DB-API connection."""

    def __init__(self, columns, rows):
        self._columns = columns
        self._rows = rows

    def cursor(self):
        """Return a fresh fake cursor over the same fixed rows."""
        return FakeCursor(self._columns, self._rows)


USER_COLUMNS = [
    "user_email",
    "user_full_name",
    "user_address_country",
    "user_address_state",
    "user_address_postal_code",
    "user_address_street_1",
    "user_address_street_2",
    "user_address_city",
    "user_gender",
    "user_birth_year",
]


def _user_row(email, name, country="US"):
    return (
        email,
        name,
        country,
        "MA",
        "02139",
        "1 Main St",
        "",
        "Cambridge",
        None,
        None,
    )


def test_bulk_create_users_returns_real_ids():
    """_bulk_create_users must return objects with real, populated ids -
    bulk_create(ignore_conflicts=True) never sets .pk on its own, on any
    backend, so this only works if the returned rows are re-fetched
    """
    rows = [{"user_email": "new@example.com", "user_full_name": "New User"}]

    created = Command._bulk_create_users(  # noqa: SLF001
        rows, existing_emails=set(), batch_size=100
    )

    assert len(created) == 1
    assert created[0].id is not None
    assert User.objects.get(email="new@example.com").id == created[0].id


def test_migrate_users_creates_legal_address_and_profile():
    """End to end through _migrate_users: new users must actually get
    LegalAddress and UserProfile rows, not just a User row
    """
    conn = FakeConnection(
        columns=USER_COLUMNS,
        rows=[_user_row("alice@example.com", "Alice A", country="US")],
    )

    Command()._migrate_users(conn, {})  # noqa: SLF001

    user = User.objects.get(email="alice@example.com")
    assert user.legal_address.country == "US"
    assert UserProfile.objects.filter(user=user).exists()


def test_migrate_users_multiple_new_users_in_one_batch():
    """Multiple new users in a single batch must each get their own
    LegalAddress - previously, every user.id was None, so id_row_lookup
    collapsed every entry onto the same None key and only one user's row
    data survived
    """
    conn = FakeConnection(
        columns=USER_COLUMNS,
        rows=[
            _user_row("alice@example.com", "Alice A", country="US"),
            _user_row("bob@example.com", "Bob B", country="CA"),
        ],
    )

    Command()._migrate_users(conn, {})  # noqa: SLF001

    alice = User.objects.get(email="alice@example.com")
    bob = User.objects.get(email="bob@example.com")
    assert alice.legal_address.country == "US"
    assert bob.legal_address.country == "CA"
    assert UserProfile.objects.filter(user=alice).exists()
    assert UserProfile.objects.filter(user=bob).exists()


def test_migrate_users_skips_existing_emails():
    """A user who already exists in mitxonline must not get a duplicate
    User row, and their existing LegalAddress/UserProfile must be left
    alone
    """
    existing_user = UserFactory.create(email="existing@example.com")
    LegalAddress.objects.filter(user=existing_user).delete()

    conn = FakeConnection(
        columns=USER_COLUMNS,
        rows=[_user_row(existing_user.email, "Existing User", country="US")],
    )

    Command()._migrate_users(conn, {})  # noqa: SLF001

    assert User.objects.filter(email=existing_user.email).count() == 1
    assert not LegalAddress.objects.filter(user=existing_user).exists()
