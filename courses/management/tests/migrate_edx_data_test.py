"""Tests for migrate_edx_data management command's repair_migrated_profiles
type and --dry-run behavior"""

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


def _break_user(user):
    """Simulate the historical bug's effect: a User row with no
    LegalAddress or UserProfile at all.
    """
    LegalAddress.objects.filter(user=user).delete()
    UserProfile.objects.filter(user=user).delete()


def test_repair_creates_missing_legal_address_and_profile():
    """A user missing both rows gets both created from the matching edX row"""
    user = UserFactory.create(email="broken@example.com")
    _break_user(user)

    conn = FakeConnection(
        columns=USER_COLUMNS,
        rows=[_user_row(user.email, "Broken User", country="US")],
    )

    Command()._repair_migrated_user_profiles(conn, {})  # noqa: SLF001

    user.refresh_from_db()
    assert user.legal_address.country == "US"
    assert UserProfile.objects.filter(user=user).exists()


def test_repair_only_backfills_missing_piece():
    """A user missing only UserProfile (LegalAddress already exists) only
    gets UserProfile created - the existing helpers must not touch or
    duplicate the LegalAddress that's already there
    """
    user = UserFactory.create(email="half-broken@example.com")
    user.legal_address.country = "CA"
    user.legal_address.save()
    UserProfile.objects.filter(user=user).delete()

    conn = FakeConnection(
        columns=USER_COLUMNS,
        rows=[_user_row(user.email, "Half Broken", country="US")],
    )

    Command()._repair_migrated_user_profiles(conn, {})  # noqa: SLF001

    user.refresh_from_db()
    assert user.legal_address.country == "CA"
    assert UserProfile.objects.filter(user=user).exists()


def test_repair_skips_users_with_no_missing_rows():
    """A user who already has both rows is left untouched, even though a
    matching edX row exists for their email
    """
    user = UserFactory.create(email="fine@example.com")
    user.legal_address.country = "MX"
    user.legal_address.save()

    conn = FakeConnection(
        columns=USER_COLUMNS,
        rows=[_user_row(user.email, "Fine User", country="US")],
    )

    Command()._repair_migrated_user_profiles(conn, {})  # noqa: SLF001

    user.refresh_from_db()
    assert user.legal_address.country == "MX"


def test_repair_leaves_unmatched_user_broken_without_crashing():
    """An affected user with no corresponding row in edxorg_to_mitxonline_users
    (e.g. their edX data was never in that table) is reported as still
    missing, not silently invented from nothing
    """
    user = UserFactory.create(email="no-edx-row@example.com")
    _break_user(user)

    conn = FakeConnection(columns=USER_COLUMNS, rows=[])

    Command()._repair_migrated_user_profiles(conn, {})  # noqa: SLF001

    assert not LegalAddress.objects.filter(user=user).exists()
    assert not UserProfile.objects.filter(user=user).exists()


def test_dry_run_does_not_write():
    """--dry-run must not create any rows, even for a clearly matched user"""
    user = UserFactory.create(email="dry-run@example.com")
    _break_user(user)

    conn = FakeConnection(
        columns=USER_COLUMNS,
        rows=[_user_row(user.email, "Dry Run User", country="US")],
    )

    Command()._repair_migrated_user_profiles(conn, {"dry_run": True})  # noqa: SLF001

    assert not LegalAddress.objects.filter(user=user).exists()
    assert not UserProfile.objects.filter(user=user).exists()


def test_limit_caps_number_of_users_repaired():
    """--limit caps how many affected users are considered at all, leaving
    the rest broken for a later run
    """
    users = [UserFactory.create(email=f"limited-{i}@example.com") for i in range(3)]
    for user in users:
        _break_user(user)

    conn = FakeConnection(
        columns=USER_COLUMNS,
        rows=[_user_row(user.email, "Limited User", country="US") for user in users],
    )

    Command()._repair_migrated_user_profiles(conn, {"limit": 1})  # noqa: SLF001

    repaired = User.objects.filter(legal_address__isnull=False).count()
    assert repaired == 1


def test_migrate_users_dry_run_creates_no_records(capsys):
    """--dry-run must not create any User/LegalAddress/UserProfile rows"""
    existing_user = UserFactory.create(email="existing@example.com")
    conn = FakeConnection(
        columns=["user_email", "user_full_name"],
        rows=[
            ("new1@example.com", "New One"),
            ("new2@example.com", "New Two"),
            (existing_user.email, "Existing User"),
        ],
    )

    Command()._migrate_users(conn, {"dry_run": True})  # noqa: SLF001

    assert User.objects.count() == 1  # only the pre-existing user
    output = capsys.readouterr().out
    assert "[DRY RUN] Would create 2 users" in output


def test_migrate_users_dry_run_respects_batching(capsys):
    """The dry-run count must accumulate correctly across multiple fetchmany
    batches, not just within a single batch
    """
    conn = FakeConnection(
        columns=["user_email", "user_full_name"],
        rows=[(f"new{i}@example.com", f"New {i}") for i in range(5)],
    )

    Command()._migrate_users(conn, {"dry_run": True, "batch_size": 2})  # noqa: SLF001

    assert User.objects.count() == 0
    output = capsys.readouterr().out
    assert "[DRY RUN] Would create 5 users" in output


def test_migrate_users_real_run_creates_user_records():
    """Without --dry-run, matching rows actually create User rows.

    Deliberately not asserting on legal_address here: _bulk_create_users
    calls User.objects.bulk_create(..., ignore_conflicts=True), and Django
    never populates .pk on returned objects when ignore_conflicts=True is
    used, on any backend - confirmed empirically against this test DB. That
    means _bulk_create_legal_addresses/_bulk_create_user_profiles, which
    filter on those (always-None) ids, never actually create anything today.
    That's a separate, pre-existing bug unrelated to --dry-run - flagged
    separately, not fixed here.
    """
    conn = FakeConnection(
        columns=["user_email", "user_full_name"],
        rows=[("new@example.com", "New User")],
    )

    Command()._migrate_users(conn, {})  # noqa: SLF001

    user = User.objects.get(email="new@example.com")
    assert user.name == "New User"
