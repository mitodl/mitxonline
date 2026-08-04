"""Tests for the sync_courserun_deadlines management command."""

from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from mitol.common.utils.datetime import now_in_utc
from requests.exceptions import HTTPError

from courses.factories import CourseRunFactory
from main import features
from openedx.constants import UpgradeDeadlineSyncResult

pytestmark = [pytest.mark.django_db]

COMMAND = "sync_courserun_deadlines"


@pytest.fixture(autouse=True)
def _enable_and_isolate(settings, mocker):
    """
    Turn the flag on and stub the edX client for every test in this module.

    The command builds one client for the batch, so that call has to be patched
    even for the paths that never issue a write.
    """
    settings.FEATURES[features.SYNC_UPGRADE_DEADLINE_TO_EDX] = True
    mocker.patch(
        "courses.management.commands.sync_courserun_deadlines.get_edx_api_service_client"
    )


@pytest.fixture
def mock_sync(mocker):
    """Patch the sync function the command calls."""
    return mocker.patch(
        "courses.management.commands.sync_courserun_deadlines.sync_courserun_upgrade_deadline_to_edx",
        return_value=UpgradeDeadlineSyncResult.UPDATED,
    )


def test_requires_run_or_all():
    """Neither --run nor --all is an error rather than a silent no-op."""
    with pytest.raises(CommandError):
        call_command(COMMAND)


def test_unknown_run_errors(mock_sync):
    """A courseware_id that does not exist should fail loudly."""
    with pytest.raises(CommandError, match="Could not find run"):
        call_command(COMMAND, run="course-v1:edX+Nope+Nope")

    mock_sync.assert_not_called()


def test_syncs_single_run(mock_sync):
    """--run syncs exactly that run."""
    run = CourseRunFactory.create(upgrade_deadline=now_in_utc() + timedelta(days=5))
    CourseRunFactory.create()
    out = StringIO()

    call_command(COMMAND, run=run.courseware_id, stdout=out)

    mock_sync.assert_called_once()
    assert mock_sync.call_args.args[0] == run
    assert run.courseware_id in out.getvalue()
    assert "updated: 1" in out.getvalue()


def test_single_run_accepts_source_runs(mock_sync):
    """
    Source/B2B runs are hidden from the default manager but still need syncing,
    so lookup has to go through all_objects.
    """
    run = CourseRunFactory.create(
        is_source_run=True, upgrade_deadline=now_in_utc() + timedelta(days=5)
    )

    call_command(COMMAND, run=run.courseware_id, stdout=StringIO())

    assert mock_sync.call_args.args[0] == run


def test_all_skips_runs_without_a_deadline(mock_sync):
    """
    Runs with no deadline are excluded: edX cannot unset an existing expiration
    date, so there is nothing useful to push for them.
    """
    with_deadline = CourseRunFactory.create(
        live=True, upgrade_deadline=now_in_utc() + timedelta(days=5)
    )
    CourseRunFactory.create(live=True, upgrade_deadline=None)

    call_command(COMMAND, all=True, stdout=StringIO())

    assert mock_sync.call_count == 1
    assert mock_sync.call_args.args[0] == with_deadline


def test_all_reuses_one_client(mock_sync):
    """
    One client for the whole batch - each get_edx_api_service_client() call
    refreshes an OAuth token, so per-run clients would be wasteful.
    """
    CourseRunFactory.create_batch(
        3, live=True, upgrade_deadline=now_in_utc() + timedelta(days=5)
    )

    call_command(COMMAND, all=True, stdout=StringIO())

    assert mock_sync.call_count == 3
    clients = {call.kwargs["client"] for call in mock_sync.call_args_list}
    assert len(clients) == 1


def test_dry_run_makes_no_calls(mock_sync):
    """--dry-run reports without touching edX."""
    run = CourseRunFactory.create(
        live=True, upgrade_deadline=now_in_utc() + timedelta(days=5)
    )
    out = StringIO()

    call_command(COMMAND, all=True, dry_run=True, stdout=out)

    mock_sync.assert_not_called()
    assert f"Would push {run.upgrade_deadline} to {run.courseware_id}" in out.getvalue()
    assert "Dry run" in out.getvalue()


def test_reports_clear_unsupported(mock_sync):
    """
    The un-clearable case gets its own line so an operator knows to go fix edX
    by hand.
    """
    run = CourseRunFactory.create(upgrade_deadline=None)
    mock_sync.return_value = UpgradeDeadlineSyncResult.CLEAR_UNSUPPORTED
    out = StringIO()

    call_command(COMMAND, run=run.courseware_id, stdout=out)

    assert "edX cannot unset" in out.getvalue()


def test_reports_missing_verified_mode(mock_sync):
    """A run with no verified mode in edX is surfaced as a warning."""
    run = CourseRunFactory.create()
    mock_sync.return_value = UpgradeDeadlineSyncResult.NO_VERIFIED_MODE
    out = StringIO()

    call_command(COMMAND, run=run.courseware_id, stdout=out)

    assert "no verified mode in edX" in out.getvalue()


def test_warns_when_feature_disabled(settings, mock_sync):
    """A disabled flag should be called out, not silently produce zero work."""
    settings.FEATURES[features.SYNC_UPGRADE_DEADLINE_TO_EDX] = False
    run = CourseRunFactory.create()
    mock_sync.return_value = UpgradeDeadlineSyncResult.DISABLED
    out = StringIO()

    call_command(COMMAND, run=run.courseware_id, stdout=out)

    assert "FEATURE_SYNC_UPGRADE_DEADLINE_TO_EDX is off" in out.getvalue()


def test_one_failure_does_not_stop_the_batch(mock_sync):
    """A single bad run must not strand the rest of the batch."""
    CourseRunFactory.create_batch(
        3, live=True, upgrade_deadline=now_in_utc() + timedelta(days=5)
    )
    mock_sync.side_effect = [
        UpgradeDeadlineSyncResult.UPDATED,
        HTTPError("boom"),
        UpgradeDeadlineSyncResult.UPDATED,
    ]
    out, err = StringIO(), StringIO()

    call_command(COMMAND, all=True, stdout=out, stderr=err)

    assert mock_sync.call_count == 3
    assert "boom" in err.getvalue()
    assert "updated: 2" in out.getvalue()
    assert "failed: 1" in out.getvalue()


def test_no_matching_runs(mock_sync):
    """--all with nothing to do says so."""
    out = StringIO()

    call_command(COMMAND, all=True, stdout=out)

    mock_sync.assert_not_called()
    assert "No matching course runs" in out.getvalue()
