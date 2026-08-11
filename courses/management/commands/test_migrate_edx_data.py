"""Tests for migrate_edx_data management command's --dry-run behavior"""

import pytest

from courses.management.commands.migrate_edx_data import Command
from users.factories import UserFactory
from users.models import User

pytestmark = pytest.mark.django_db


class FakeCursor:
    """Minimal stand-in for a Trino DB-API cursor."""

    def __init__(self, columns, rows):
        self.description = [(col,) for col in columns]
        self._rows = rows
        self._offset = 0

    def execute(self, query):
        pass

    def fetchmany(self, size):
        batch = self._rows[self._offset : self._offset + size]
        self._offset += size
        return batch


class FakeConnection:
    """Minimal stand-in for a Trino DB-API connection."""

    def __init__(self, columns, rows):
        self._columns = columns
        self._rows = rows

    def cursor(self):
        return FakeCursor(self._columns, self._rows)


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
