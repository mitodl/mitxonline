"""Tests for migrate_and_sync_users management command"""

import json
from types import SimpleNamespace

import pytest
from django.core.management import CommandError
from django.db import connection
from django.test.utils import CaptureQueriesContext

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
@pytest.mark.parametrize("batch_size", [0, -1, -250])
def test_non_positive_batch_size_is_rejected(mock_edx_migration, batch_size):
    """A non-positive --batch-size must fail fast, before Stage 1 even runs -
    range(0, len(to_sync), batch_size) silently performs zero iterations for
    a negative step, which would skip Stage 3 entirely for a nonempty
    to_sync list while the command still reports a "successful" run.
    """
    with pytest.raises(CommandError, match="--batch-size must be a positive"):
        COMMAND.handle(
            dry_run=False,
            skip_edx_migration=False,
            force=False,
            limit=None,
            batch_size=batch_size,
        )

    mock_edx_migration.assert_not_called()


@pytest.mark.django_db
def test_limit_is_threaded_through_to_migrate_edx_data(mock_edx_migration, mocker):
    """--limit should also limit Stage 1's Trino query, not just which
    mitxonline candidates get classified/synced - otherwise a small test run
    still backfills the entire edX dataset before test-syncing a handful
    of users
    """
    mocker.patch(
        "users.management.commands.migrate_and_sync_users.scim_api.sync_users_to_scim_remote",
        return_value=[],
    )

    COMMAND.handle(dry_run=False, skip_edx_migration=False, force=False, limit=5)

    mock_edx_migration.assert_called_once_with(
        "migrate_edx_data", type="users", limit=5
    )


@pytest.mark.django_db
def test_no_limit_does_not_pass_limit_kwarg(mock_edx_migration, mocker):
    """Without --limit, migrate_edx_data should run with its own default
    (unbounded), not an explicit limit=None which would behave differently
    if migrate_edx_data ever starts treating limit=None as limit=0
    """
    mocker.patch(
        "users.management.commands.migrate_and_sync_users.scim_api.sync_users_to_scim_remote",
        return_value=[],
    )

    COMMAND.handle(dry_run=False, skip_edx_migration=False, force=False, limit=None)

    mock_edx_migration.assert_called_once_with("migrate_edx_data", type="users")


@pytest.mark.django_db
def test_classify_avoids_n_plus_one_queries(mocker, django_assert_max_num_queries):
    """Stage 2's candidate query plus classifying every candidate must not
    issue extra queries per user - LearnUserAdapter.__init__ touches
    user_profile and the openedx_user cached_property on every
    instantiation, so both need to be covered by handle()'s bulk
    select_related/prefetch_related, not fetched one-by-one per candidate.
    """
    mocker.patch(
        "users.management.commands.migrate_and_sync_users.scim_api.sync_users_to_scim_remote",
        return_value=[],
    )
    for _ in range(5):
        user = UserFactory.create(name="Joe Smith", global_id=None)
        user.legal_address.first_name = "Joe"
        user.legal_address.last_name = "Smith"
        user.legal_address.save()

    with django_assert_max_num_queries(3):
        COMMAND.handle(
            dry_run=True,
            skip_edx_migration=True,
            force=False,
            limit=None,
            report_path=None,
        )


@pytest.mark.django_db
def test_get_candidates_applies_limit_in_sql():
    """--limit must be applied at the queryset level (a SQL LIMIT), not by
    slicing an already-materialized list - otherwise a small --limit for
    testing still fetches and prefetches every unsynced user in the table.
    """
    for _ in range(5):
        user = UserFactory.create(name="Joe Smith", global_id=None)
        user.legal_address.first_name = "Joe"
        user.legal_address.last_name = "Smith"
        user.legal_address.save()

    with CaptureQueriesContext(connection) as ctx:
        candidates = migrate_and_sync_users.Command()._get_candidates(limit=2)  # noqa: SLF001

    assert len(candidates) == 2
    assert "LIMIT 2" in ctx.captured_queries[0]["sql"]


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

    tier_by_user_id = {row["user_id"]: row["tier"] for row in report["to_sync"]}
    assert tier_by_user_id[tier2_user.id] == "full_name_only"


@pytest.mark.django_db
def test_full_name_only_user_is_not_blocked(mocker, tmp_path):
    """A user with a full name (User.name) but no legal_address split is
    classified as "full_name_only" and synced by default, not blocked -
    LearnUserAdapter._resolve_name() no longer guesses a given/family split
    from User.name (see users/adapters.py), so tier can't be based on
    given_name/family_name being non-blank anymore. This is the common
    edxorg-migration case, and it's exactly the population migrate_edx_data's
    bulk_create bug (fixed separately in #3843) leaves without a
    legal_address row at all - they must not be silently gated behind
    --force just because the split-name signal is gone.
    """
    mocker.patch(
        "users.management.commands.migrate_and_sync_users.scim_api.sync_users_to_scim_remote",
        return_value=[],
    )

    user = UserFactory.create(name="Jane Doe", global_id=None)
    user.legal_address.delete()

    report = _run(
        tmp_path, dry_run=True, skip_edx_migration=False, force=False, limit=None
    )

    assert report["blocked"] == []
    row = next(row for row in report["to_sync"] if row["user_id"] == user.id)
    assert row["tier"] == "full_name_only"
    assert row["given_name"] == ""
    assert row["family_name"] == ""


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
def test_handles_sync_users_to_scim_remote_as_a_real_generator(mocker, tmp_path):
    """sync_users_to_scim_remote is a generator in real mitol-django-scim -
    it does nothing until iterated and can't be iterated twice. The mocks
    in other tests return plain lists, which would mask a regression back
    to `len(states)`/multi-pass iteration over a bare generator, so this
    exercises a real one-shot generator to confirm Stage 3/4 only iterate
    it once.
    """
    user = UserFactory.create(name="Joe Smith", global_id=None)
    user.legal_address.first_name = "Joe"
    user.legal_address.last_name = "Smith"
    user.legal_address.save()

    def _one_shot_states(users):
        for synced_user in users:
            yield _state(
                synced_user,
                response_body={"name": {"givenName": "Joe", "familyName": "Smith"}},
            )

    mocker.patch(
        "users.management.commands.migrate_and_sync_users.scim_api.sync_users_to_scim_remote",
        side_effect=_one_shot_states,
    )

    report = _run(
        tmp_path, dry_run=False, skip_edx_migration=False, force=False, limit=None
    )

    assert [row["user_id"] for row in report["verified"]] == [user.id]
    assert report["mismatched"] == []


@pytest.mark.django_db
def test_verifies_blank_name_when_response_body_omits_name(mocker, tmp_path):
    """A tier-3 (forced blank name) user's response body omitting "name"
    entirely must still verify - sent ("", "") should match an absent name,
    not be flagged as a mismatch
    """
    user = UserFactory.create(name="", global_id=None)
    user.legal_address.first_name = ""
    user.legal_address.last_name = ""
    user.legal_address.save()

    mocker.patch(
        "users.management.commands.migrate_and_sync_users.scim_api.sync_users_to_scim_remote",
        return_value=[_state(user, response_body={})],
    )

    report = _run(
        tmp_path, dry_run=False, skip_edx_migration=False, force=True, limit=None
    )

    assert [row["user_id"] for row in report["verified"]] == [user.id]
    assert report["mismatched"] == []


@pytest.mark.django_db
def test_verifies_blank_name_when_response_body_has_explicit_null_name(
    mocker, tmp_path
):
    """A response body with "name": null (present, not omitted) must not
    crash - .get("name", {}) returns None itself in that case, and calling
    .get() on it would raise AttributeError without a guard
    """
    user = UserFactory.create(name="", global_id=None)
    user.legal_address.first_name = ""
    user.legal_address.last_name = ""
    user.legal_address.save()

    mocker.patch(
        "users.management.commands.migrate_and_sync_users.scim_api.sync_users_to_scim_remote",
        return_value=[_state(user, response_body={"name": None})],
    )

    report = _run(
        tmp_path, dry_run=False, skip_edx_migration=False, force=True, limit=None
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
