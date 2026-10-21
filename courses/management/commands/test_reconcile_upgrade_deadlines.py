"""Tests for the reconcile_upgrade_deadlines management command."""

import csv
from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from edx_api.course_detail.models import CourseMode
from mitol.common.utils.datetime import now_in_utc
from requests.exceptions import HTTPError

from courses.factories import CourseRunFactory
from openedx.constants import EDX_ENROLLMENT_VERIFIED_MODE, UpgradeDeadlineSyncResult

pytestmark = [pytest.mark.django_db]

COMMAND = "reconcile_upgrade_deadlines"
MODULE = "courses.management.commands.reconcile_upgrade_deadlines"


@pytest.fixture(autouse=True)
def mock_edx_client(mocker):
    """Stub the edX client so no test reaches edX."""
    return mocker.patch(f"{MODULE}.get_edx_api_service_client")


@pytest.fixture
def mock_verified_mode(mocker):
    """Patch the verified mode lookup the command uses."""
    return mocker.patch(f"{MODULE}.get_edx_verified_mode")


def _verified_mode(expiration_datetime, *, is_explicit=True):
    """Build a verified CourseMode with the given expiration."""
    return CourseMode(
        {
            "course_id": "course-v1:edX+Test+Run",
            "mode_slug": EDX_ENROLLMENT_VERIFIED_MODE,
            "mode_display_name": "Verified",
            "min_price": 100,
            "currency": "usd",
            "expiration_datetime": (
                expiration_datetime.isoformat() if expiration_datetime else None
            ),
            "expiration_datetime_is_explicit": is_explicit,
        }
    )


def _run_command(*, expect_failure=False, **kwargs):
    """
    Run the command and return its CSV rows (without the header) and stderr.

    With expect_failure, assert the command ends with a CommandError (a row
    errored or failed) and return its message as the stderr.
    """
    out, err = StringIO(), StringIO()
    if expect_failure:
        with pytest.raises(CommandError) as exc_info:
            call_command(COMMAND, stdout=out, stderr=err, **kwargs)
        err.write(str(exc_info.value))
    else:
        call_command(COMMAND, stdout=out, stderr=err, **kwargs)
    rows = list(csv.DictReader(StringIO(out.getvalue())))
    return rows, err.getvalue()


def test_requires_run_or_all():
    """Neither --run nor --all is an error rather than a silent no-op."""
    with pytest.raises(CommandError):
        call_command(COMMAND)


def test_unknown_run_errors(mock_verified_mode):
    """A courseware_id that doesn't exist should fail loudly."""
    with pytest.raises(CommandError, match="Could not find run"):
        call_command(COMMAND, run="course-v1:edX+Nope+Nope")

    mock_verified_mode.assert_not_called()


@pytest.mark.parametrize(
    ("mxo_offset", "edx_offset", "is_explicit", "expected_status"),
    [
        (10, 10, True, "ok"),
        (10, 10, False, "unpinned"),
        (None, None, False, "ok"),
        (None, 10, True, "mxo_missing"),
        (10, 20, True, "mismatch"),
        (10, None, False, "edx_missing"),
    ],
)
def test_reports_status(
    mock_verified_mode, mxo_offset, edx_offset, is_explicit, expected_status
):
    """Each combination of MITx Online and edX deadlines gets the right status."""
    now = now_in_utc().replace(microsecond=0)
    mxo_deadline = now + timedelta(days=mxo_offset) if mxo_offset else None
    edx_deadline = now + timedelta(days=edx_offset) if edx_offset else None
    run = CourseRunFactory.create(upgrade_deadline=mxo_deadline)
    mock_verified_mode.return_value = _verified_mode(
        edx_deadline, is_explicit=is_explicit
    )

    rows, _ = _run_command(run=run.courseware_id)

    assert rows == [
        {
            "courseware_id": run.courseware_id,
            "mxo_deadline": mxo_deadline.isoformat() if mxo_deadline else "",
            "edx_deadline": edx_deadline.isoformat() if edx_deadline else "",
            "status": expected_status,
            "fixed": "",
        }
    ]


def test_report_only_changes_nothing(mock_verified_mode):
    """Without --fix, a mismatched run is reported but left alone."""
    mxo_deadline = now_in_utc().replace(microsecond=0) + timedelta(days=10)
    run = CourseRunFactory.create(upgrade_deadline=mxo_deadline)
    mock_verified_mode.return_value = _verified_mode(mxo_deadline + timedelta(days=5))

    rows, err = _run_command(run=run.courseware_id)

    run.refresh_from_db()
    assert run.upgrade_deadline == mxo_deadline
    assert rows[0]["status"] == "mismatch"
    assert "run with --fix" in err


@pytest.mark.parametrize("mxo_offset", [None, 10])
def test_fix_copies_edx_deadline(
    mocker, django_capture_on_commit_callbacks, mock_verified_mode, mxo_offset
):
    """
    --fix copies the edX deadline into MITx Online for missing and mismatched
    runs, and saves the run so the Fastly purge runs.
    """
    now = now_in_utc().replace(microsecond=0)
    edx_deadline = now + timedelta(days=30)
    run = CourseRunFactory.create(
        upgrade_deadline=now + timedelta(days=mxo_offset) if mxo_offset else None
    )
    mock_verified_mode.return_value = _verified_mode(edx_deadline)
    mock_purge = mocker.patch("cms.tasks.queue_fastly_surrogate_key_purge.delay")
    mock_push = mocker.patch("courses.tasks.sync_courserun_upgrade_deadline.delay")

    with django_capture_on_commit_callbacks(execute=True):
        rows, _ = _run_command(run=run.courseware_id, fix=True)

    run.refresh_from_db()
    assert run.upgrade_deadline == edx_deadline
    assert rows[0]["fixed"] == "yes"
    mock_purge.assert_called_once()
    # The push is queued because the deadline changed. It sends edX its own
    # date back, which pins it.
    mock_push.assert_called_once_with(run.id)


@pytest.mark.parametrize("status_offsets", [(10, None), (None, None)])
def test_fix_leaves_unfixable_runs_alone(mock_verified_mode, status_offsets):
    """
    --fix never clears a MITx Online deadline (edx_missing) and doesn't touch
    runs that already match.
    """
    mxo_offset, edx_offset = status_offsets
    now = now_in_utc().replace(microsecond=0)
    mxo_deadline = now + timedelta(days=mxo_offset) if mxo_offset else None
    run = CourseRunFactory.create(upgrade_deadline=mxo_deadline)
    mock_verified_mode.return_value = _verified_mode(
        now + timedelta(days=edx_offset) if edx_offset else None
    )

    rows, _ = _run_command(run=run.courseware_id, fix=True)

    run.refresh_from_db()
    assert run.upgrade_deadline == mxo_deadline
    assert rows[0]["fixed"] == ""


def test_fix_continues_past_a_run_that_fails_validation(mock_verified_mode):
    """
    CourseRun.save() runs clean(), which can reject a run for reasons unrelated
    to its deadline. That run is reported as failed and the rest still get fixed.
    """
    now = now_in_utc().replace(microsecond=0)
    edx_deadline = now + timedelta(days=30)
    broken, valid = sorted(
        CourseRunFactory.create_batch(2, live=True, upgrade_deadline=None),
        key=lambda run: run.courseware_id,
    )
    # An expiration date before the end date fails clean(). update() skips it,
    # the way older rows got into this state.
    type(broken).objects.filter(pk=broken.pk).update(
        expiration_date=broken.end_date - timedelta(days=1)
    )
    mock_verified_mode.return_value = _verified_mode(edx_deadline)

    rows, err = _run_command(all=True, fix=True, expect_failure=True)

    assert [(row["courseware_id"], row["fixed"]) for row in rows] == [
        (broken.courseware_id, "failed"),
        (valid.courseware_id, "yes"),
    ]
    assert f"{broken.courseware_id}: could not save" in err
    assert "Fixed: 1, failed: 1" in err
    broken.refresh_from_db()
    valid.refresh_from_db()
    assert broken.upgrade_deadline is None
    assert valid.upgrade_deadline == edx_deadline


def test_no_verified_mode(mock_verified_mode):
    """A run without a verified mode in edX is reported and not fixed."""
    run = CourseRunFactory.create()
    mock_verified_mode.return_value = None

    rows, _ = _run_command(run=run.courseware_id, fix=True)

    assert rows[0]["status"] == "no_verified_mode"
    assert rows[0]["fixed"] == ""


def test_all_selects_current_runs(mock_verified_mode):
    """
    --all checks live, unexpired runs that haven't ended, and skips fake- runs,
    non-live runs and runs that have already ended.
    """
    now = now_in_utc()
    current = CourseRunFactory.create(live=True)
    no_end = CourseRunFactory.create(live=True, end_date=None)
    CourseRunFactory.create(live=False)
    CourseRunFactory.create(live=True, run_tag="fake-run")
    CourseRunFactory.create(
        live=True,
        start_date=now - timedelta(days=60),
        end_date=now - timedelta(days=1),
        expiration_date=now + timedelta(days=30),
    )
    mock_verified_mode.return_value = _verified_mode(None)

    rows, _ = _run_command(all=True)

    assert {row["courseware_id"] for row in rows} == {
        current.courseware_id,
        no_end.courseware_id,
    }


@pytest.mark.parametrize("fix", [False, True])
def test_one_failure_does_not_stop_the_report(mock_verified_mode, fix):
    """
    An edX error on one run is reported (with the error type) and the rest still
    get checked. --fix leaves the errored run alone, and the command fails at
    the end so a script can tell.
    """
    deadline = now_in_utc().replace(microsecond=0) + timedelta(days=10)
    runs = sorted(
        CourseRunFactory.create_batch(2, live=True, upgrade_deadline=deadline),
        key=lambda run: run.courseware_id,
    )
    mock_verified_mode.side_effect = [HTTPError("boom"), _verified_mode(deadline)]

    rows, err = _run_command(all=True, fix=fix, expect_failure=True)

    assert [(row["status"], row["fixed"]) for row in rows] == [
        ("error", ""),
        ("ok", ""),
    ]
    assert f"{runs[0].courseware_id}: HTTPError: boom" in err
    assert "error: 1" in err
    runs[0].refresh_from_db()
    assert runs[0].upgrade_deadline == deadline


def test_programming_errors_are_not_swallowed(mock_verified_mode):
    """Only edX request errors are reported per row; a bug still raises."""
    run = CourseRunFactory.create(live=True)
    mock_verified_mode.side_effect = AttributeError("bug")

    with pytest.raises(AttributeError, match="bug"):
        _run_command(run=run.courseware_id)


def test_fix_pins_unpinned_run(mocker, mock_verified_mode, mock_edx_client):
    """
    A matching date that edX hasn't marked explicit is pushed back to edX, which
    pins it. MITx Online's deadline doesn't change.
    """
    deadline = now_in_utc().replace(microsecond=0) + timedelta(days=10)
    run = CourseRunFactory.create(upgrade_deadline=deadline)
    mock_verified_mode.return_value = _verified_mode(deadline, is_explicit=False)
    mock_pin = mocker.patch(
        f"{MODULE}.sync_courserun_upgrade_deadline_to_edx",
        return_value=UpgradeDeadlineSyncResult.UPDATED,
    )

    rows, _ = _run_command(run=run.courseware_id, fix=True)

    assert [(row["status"], row["fixed"]) for row in rows] == [("unpinned", "yes")]
    mock_pin.assert_called_once_with(run, client=mock_edx_client.return_value)
    run.refresh_from_db()
    assert run.upgrade_deadline == deadline


def test_report_only_does_not_pin(mocker, mock_verified_mode):
    """Without --fix, an unpinned run is only reported."""
    deadline = now_in_utc().replace(microsecond=0) + timedelta(days=10)
    run = CourseRunFactory.create(upgrade_deadline=deadline)
    mock_verified_mode.return_value = _verified_mode(deadline, is_explicit=False)
    mock_pin = mocker.patch(f"{MODULE}.sync_courserun_upgrade_deadline_to_edx")

    rows, _ = _run_command(run=run.courseware_id)

    assert rows[0]["status"] == "unpinned"
    mock_pin.assert_not_called()


def test_fix_reports_failed_pin(mocker, mock_verified_mode):
    """An edX error while pinning marks the row failed and fails the command."""
    deadline = now_in_utc().replace(microsecond=0) + timedelta(days=10)
    run = CourseRunFactory.create(upgrade_deadline=deadline)
    mock_verified_mode.return_value = _verified_mode(deadline, is_explicit=False)
    mocker.patch(
        f"{MODULE}.sync_courserun_upgrade_deadline_to_edx",
        side_effect=HTTPError("boom"),
    )

    rows, err = _run_command(run=run.courseware_id, fix=True, expect_failure=True)

    assert rows[0]["fixed"] == "failed"
    assert f"{run.courseware_id}: could not pin: HTTPError: boom" in err


def test_delay_between_requests(mocker, mock_verified_mode):
    """--delay sleeps between edX requests, not before the first one."""
    mock_sleep = mocker.patch(f"{MODULE}.time.sleep")
    CourseRunFactory.create_batch(3, live=True)
    mock_verified_mode.return_value = _verified_mode(None)

    _run_command(all=True, delay=1.5)

    assert mock_sleep.call_count == 2
    mock_sleep.assert_called_with(1.5)
