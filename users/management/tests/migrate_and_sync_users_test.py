"""Tests for migrate_and_sync_users management command"""

import json
from types import SimpleNamespace

import pytest

from users.factories import UserFactory
from users.management.commands import migrate_and_sync_users

COMMAND = migrate_and_sync_users.Command()


def _state(user, *, success=True, response_body=None, error=None, external_id="ext"):
    """Build a fake UserState-like object, decoupled from whatever version of
    mitol-django-scim happens to be installed - the command only duck-types
    on .user/.success/.response_body/.error.
    """
    return SimpleNamespace(
        user=user,
        success=success,
        external_id=external_id if success else None,
        response_body=response_body,
        error=error,
    )


def _run(tmp_path, **options):
    """Run the command and return its parsed JSON report - reading the report
    file, rather than scraping stdout, avoids Command()'s stdout reference
    being grabbed at module-import time (before pytest's capture fixtures are
    active for the current test).
    """
    report_path = tmp_path / "report.json"
    COMMAND.handle(report_path=str(report_path), **options)
    return json.loads(report_path.read_text())


@pytest.fixture(autouse=True)
def mock_edx_migration(mocker):
    """Stage 1 always gets skipped/mocked in these tests - never hit Trino."""
    return mocker.patch("users.management.commands.migrate_and_sync_users.call_command")


@pytest.mark.django_db
def test_dry_run_classifies_without_syncing(mocker, tmp_path):
    """Dry run reports classification tiers and never calls the sync API"""
    mock_sync = mocker.patch(
        "users.management.commands.migrate_and_sync_users.scim_api.sync_users_to_scim_remote"
    )

    tier1_user = UserFactory.create(name="Joe Smith", global_id=None)
    tier1_user.legal_address.first_name = "Joe"
    tier1_user.legal_address.last_name = "Smith"
    tier1_user.legal_address.save()

    tier2_user = UserFactory.create(name="Jane Doe", global_id=None)
    tier2_user.legal_address.first_name = ""
    tier2_user.legal_address.last_name = ""
    tier2_user.legal_address.save()

    tier3_user = UserFactory.create(name="", global_id=None)
    tier3_user.legal_address.first_name = ""
    tier3_user.legal_address.last_name = ""
    tier3_user.legal_address.save()

    report = _run(
        tmp_path, dry_run=True, skip_edx_migration=False, force=False, limit=None
    )

    mock_sync.assert_not_called()

    to_sync_ids = {row["user_id"] for row in report["to_sync"]}
    blocked_ids = {row["user_id"] for row in report["blocked"]}
    assert tier1_user.id in to_sync_ids
    assert tier2_user.id in to_sync_ids
    assert tier3_user.id in blocked_ids


@pytest.mark.django_db
def test_tier3_blocked_without_force(mocker):
    """A user with no name data anywhere is excluded from the sync call by default"""
    mock_sync = mocker.patch(
        "users.management.commands.migrate_and_sync_users.scim_api.sync_users_to_scim_remote",
        return_value=[],
    )

    tier1_user = UserFactory.create(name="Joe Smith", global_id=None)
    tier1_user.legal_address.first_name = "Joe"
    tier1_user.legal_address.last_name = "Smith"
    tier1_user.legal_address.save()

    tier3_user = UserFactory.create(name="", global_id=None)
    tier3_user.legal_address.first_name = ""
    tier3_user.legal_address.last_name = ""
    tier3_user.legal_address.save()

    mock_sync.side_effect = lambda users: [_state(u) for u in users]

    COMMAND.handle(dry_run=False, skip_edx_migration=False, force=False, limit=None)

    synced_users = mock_sync.call_args[0][0]
    assert tier1_user in synced_users
    assert tier3_user not in synced_users


@pytest.mark.django_db
def test_tier3_synced_with_force(mocker):
    """--force syncs a no-name-data user anyway, with a blank name"""
    mock_sync = mocker.patch(
        "users.management.commands.migrate_and_sync_users.scim_api.sync_users_to_scim_remote"
    )

    tier3_user = UserFactory.create(name="", global_id=None)
    tier3_user.legal_address.first_name = ""
    tier3_user.legal_address.last_name = ""
    tier3_user.legal_address.save()

    mock_sync.side_effect = lambda users: [_state(u) for u in users]

    COMMAND.handle(dry_run=False, skip_edx_migration=False, force=True, limit=None)

    synced_users = mock_sync.call_args[0][0]
    assert tier3_user in synced_users


@pytest.mark.django_db
def test_verifies_matching_response_body(mocker, tmp_path):
    """A synced user whose echoed response matches what was sent is verified"""
    user = UserFactory.create(name="Joe Smith", global_id=None)
    user.legal_address.first_name = "Joe"
    user.legal_address.last_name = "Smith"
    user.legal_address.save()

    mocker.patch(
        "users.management.commands.migrate_and_sync_users.scim_api.sync_users_to_scim_remote",
        return_value=[
            _state(
                user,
                response_body={"name": {"givenName": "Joe", "familyName": "Smith"}},
            )
        ],
    )

    report = _run(
        tmp_path, dry_run=False, skip_edx_migration=False, force=False, limit=None
    )

    assert [row["user_id"] for row in report["verified"]] == [user.id]
    assert report["mismatched"] == []


@pytest.mark.django_db
def test_flags_mismatched_response_body(mocker, tmp_path):
    """A synced user whose echoed response doesn't match what was sent is flagged,
    not silently counted as a success
    """
    user = UserFactory.create(name="Joe Smith", global_id=None)
    user.legal_address.first_name = "Joe"
    user.legal_address.last_name = "Smith"
    user.legal_address.save()

    mocker.patch(
        "users.management.commands.migrate_and_sync_users.scim_api.sync_users_to_scim_remote",
        return_value=[
            _state(
                user,
                response_body={"name": {"givenName": "", "familyName": ""}},
            )
        ],
    )

    report = _run(
        tmp_path, dry_run=False, skip_edx_migration=False, force=False, limit=None
    )

    assert report["verified"] == []
    assert [row["user_id"] for row in report["mismatched"]] == [user.id]


@pytest.mark.django_db
def test_failed_sync_is_reported_not_swallowed(mocker, tmp_path):
    """A failed SCIM operation is reported distinctly, not counted as a success"""
    user = UserFactory.create(name="Joe Smith", global_id=None)
    user.legal_address.first_name = "Joe"
    user.legal_address.last_name = "Smith"
    user.legal_address.save()

    mocker.patch(
        "users.management.commands.migrate_and_sync_users.scim_api.sync_users_to_scim_remote",
        return_value=[
            _state(user, success=False, error={"status": "409"}),
        ],
    )

    report = _run(
        tmp_path, dry_run=False, skip_edx_migration=False, force=False, limit=None
    )

    assert report["verified"] == []
    blocked_row = next(row for row in report["blocked"] if row["user_id"] == user.id)
    assert blocked_row["outcome"] == "failed"
    assert blocked_row["error"] == {"status": "409"}
