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
from openedx.constants import EDX_ENROLLMENT_VERIFIED_MODE

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


def _verified_mode(expiration_datetime):
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
        }
    )


def _run_command(**kwargs):
    """Run the command and return its CSV rows (without the header) and stderr."""
    out, err = StringIO(), StringIO()
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
    ("mxo_offset", "edx_offset", "expected_status"),
    [
        (10, 10, "ok"),
        (None, None, "ok"),
        (None, 10, "mxo_missing"),
        (10, 20, "mismatch"),
        (10, None, "edx_missing"),
    ],
)
def test_reports_status(mock_verified_mode, mxo_offset, edx_offset, expected_status):
    """Each combination of MITx Online and edX deadlines gets the right status."""
    now = now_in_utc().replace(microsecond=0)
    mxo_deadline = now + timedelta(days=mxo_offset) if mxo_offset else None
    edx_deadline = now + timedelta(days=edx_offset) if edx_offset else None
    run = CourseRunFactory.create(upgrade_deadline=mxo_deadline)
    mock_verified_mode.return_value = _verified_mode(edx_deadline)

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

    rows, err = _run_command(all=True, fix=True)

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


def test_one_failure_does_not_stop_the_report(mock_verified_mode):
    """An edX error on one run is reported and the rest still get checked."""
    deadline = now_in_utc().replace(microsecond=0) + timedelta(days=10)
    runs = sorted(
        CourseRunFactory.create_batch(2, live=True, upgrade_deadline=deadline),
        key=lambda run: run.courseware_id,
    )
    mock_verified_mode.side_effect = [HTTPError("boom"), _verified_mode(deadline)]

    rows, err = _run_command(all=True)

    assert [row["status"] for row in rows] == ["error", "ok"]
    assert f"{runs[0].courseware_id}: boom" in err


def test_delay_between_requests(mocker, mock_verified_mode):
    """--delay sleeps between edX requests, not before the first one."""
    mock_sleep = mocker.patch(f"{MODULE}.time.sleep")
    CourseRunFactory.create_batch(3, live=True)
    mock_verified_mode.return_value = _verified_mode(None)

    _run_command(all=True, delay=1.5)

    assert mock_sleep.call_count == 2
    mock_sleep.assert_called_with(1.5)
