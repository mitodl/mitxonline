"""
Tests for signals
"""

from datetime import timedelta
from unittest.mock import patch

import pytest
from mitol.common.utils.datetime import now_in_utc

from courses.factories import (
    CourseFactory,
    CourseRunCertificateFactory,
    CourseRunFactory,
    ProgramCertificateFactory,
    ProgramFactory,
    UserFactory,
)
from courses.models import CourseRun

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def mock_certificate_hubspot_sync_tasks(mocker):
    """Mock certificate HubSpot sync tasks to avoid external API calls in signal tests."""
    return {
        "course_run": mocker.patch(
            "courses.signals.hubspot_tasks.sync_course_run_certificate_with_hubspot.delay"
        ),
        "program": mocker.patch(
            "courses.signals.hubspot_tasks.sync_program_certificate_with_hubspot.delay"
        ),
    }


# pylint: disable=unused-argument
@patch("courses.signals.transaction.on_commit", side_effect=lambda callback: callback())
@patch("courses.signals.generate_multiple_programs_certificate", autospec=True)
def test_create_course_certificate(generate_program_cert_mock, mock_on_commit, mocker):
    """
    Test that generate_multiple_programs_certificate is called when a course
    certificate is created
    """
    user = UserFactory.create()
    course_run = CourseRunFactory.create()
    program = ProgramFactory.create()
    program.add_requirement(course_run.course)
    cert = CourseRunCertificateFactory.create(user=user, course_run=course_run)
    generate_program_cert_mock.assert_called_once_with(user, [program])
    cert.save()
    generate_program_cert_mock.assert_called_once_with(user, [program])


@patch("courses.signals.transaction.on_commit", side_effect=lambda callback: callback())
@patch("courses.signals.generate_multiple_programs_certificate", autospec=True)
def test_generate_program_certificate_if_not_live(
    generate_program_cert_mock, mock_on_commit, mocker
):
    """
    Test that generate_multiple_programs_certificate is not called when a program is not live
    """
    user = UserFactory.create()
    course_run = CourseRunFactory.create()
    program = ProgramFactory.create(live=False)
    program.add_requirement(course_run.course)
    cert = CourseRunCertificateFactory.create(user=user, course_run=course_run)
    generate_program_cert_mock.assert_not_called()
    cert.save()
    generate_program_cert_mock.assert_not_called()


# pylint: disable=unused-argument
@patch("courses.signals.transaction.on_commit", side_effect=lambda callback: callback())
@patch("courses.signals.generate_multiple_programs_certificate", autospec=True)
def test_generate_program_certificate_not_called(
    generate_program_cert_mock, mock_on_commit, mocker
):
    """
    Test that generate_multiple_programs_certificate is not called when a course
    is not associated with program.
    """
    user = UserFactory.create()
    course = CourseFactory.create()
    course_run = CourseRunFactory.create(course=course)
    cert = CourseRunCertificateFactory.create(user=user, course_run=course_run)
    cert.save()
    generate_program_cert_mock.assert_not_called()


@patch("courses.signals.transaction.on_commit", side_effect=lambda callback: callback())
def test_sync_course_certificate_with_hubspot_on_save(
    mock_on_commit, mock_certificate_hubspot_sync_tasks
):
    """Test that course certificate HubSpot sync is triggered on create and update."""
    sync_course_cert_mock = mock_certificate_hubspot_sync_tasks["course_run"]
    cert = CourseRunCertificateFactory.create()

    sync_course_cert_mock.assert_called_once_with(cert.id)

    cert.issue_date = cert.issue_date
    cert.save()

    assert sync_course_cert_mock.call_count == 2
    sync_course_cert_mock.assert_called_with(cert.id)


@patch("courses.signals.transaction.on_commit", side_effect=lambda callback: callback())
def test_sync_program_certificate_with_hubspot_on_save(
    mock_on_commit, mock_certificate_hubspot_sync_tasks
):
    """Test that program certificate HubSpot sync is triggered on create and update."""
    sync_program_cert_mock = mock_certificate_hubspot_sync_tasks["program"]
    cert = ProgramCertificateFactory.create()

    sync_program_cert_mock.assert_called_once_with(cert.id)

    cert.issue_date = cert.issue_date
    cert.save()

    assert sync_program_cert_mock.call_count == 2
    sync_program_cert_mock.assert_called_with(cert.id)


# ---------------------------------------------------------------------------
# Fastly surrogate-key purge signal tests
# ---------------------------------------------------------------------------


@patch("courses.signals.transaction.on_commit", side_effect=lambda callback: callback())
@patch("cms.tasks.queue_fastly_surrogate_key_purge.delay")
def test_purge_fastly_cache_on_course_save_update(mock_purge_delay, mock_on_commit):
    """
    Updating (re-saving) a Course enqueues a fresh purge each time.
    """
    course = CourseFactory.create()
    mock_purge_delay.assert_called_with(f"mitxonline:course:{course.readable_id}")

    course.title = "Updated Title"
    course.save()

    mock_purge_delay.assert_called_with(f"mitxonline:course:{course.readable_id}")


@patch("courses.signals.transaction.on_commit", side_effect=lambda callback: callback())
@patch("cms.tasks.queue_fastly_surrogate_key_purge.delay")
def test_purge_fastly_cache_on_course_run_save(mock_purge_delay, mock_on_commit):
    """
    Saving a CourseRun enqueues a Fastly surrogate-key purge for the parent
    course: mitxonline:course:<readable_id>.
    """
    course_run = CourseRunFactory.create()
    mock_purge_delay.assert_called_with(
        f"mitxonline:course:{course_run.course.readable_id}"
    )


@patch("courses.signals.transaction.on_commit", side_effect=lambda callback: callback())
@patch("cms.tasks.queue_fastly_surrogate_key_purge.delay")
def test_purge_fastly_cache_on_program_save(mock_purge_delay, mock_on_commit):
    """
    Saving a Program enqueues a Fastly surrogate-key purge for
    mitxonline:program:<readable_id>.
    """
    program = ProgramFactory.create()
    mock_purge_delay.assert_called_with(f"mitxonline:program:{program.readable_id}")


@pytest.fixture
def mock_deadline_sync_task(mocker):
    """
    Patch the deadline sync task's delay and make on_commit fire immediately.

    pytest-django wraps each test in a transaction that is rolled back, so
    on_commit callbacks would otherwise never run.
    """
    mocker.patch(
        "courses.signals.transaction.on_commit", side_effect=lambda callback: callback()
    )
    return mocker.patch("courses.tasks.sync_courserun_upgrade_deadline.delay")


def test_upgrade_deadline_change_queues_edx_sync(mock_deadline_sync_task):
    """Editing upgrade_deadline should queue a push to edX."""
    run = CourseRunFactory.create()
    mock_deadline_sync_task.reset_mock()

    run.upgrade_deadline = now_in_utc() + timedelta(days=45)
    run.save()

    mock_deadline_sync_task.assert_called_once_with(run.id)


def test_unrelated_save_does_not_queue_edx_sync(mock_deadline_sync_task):
    """
    Saving a run without touching upgrade_deadline must not call edX.

    The nightly sync_course_runs task saves every live run, so a signal that
    fired on any save would hammer edX with pointless writes - and each write
    sets expiration_datetime_is_explicit in edX.
    """
    run = CourseRunFactory.create()
    mock_deadline_sync_task.reset_mock()

    run.title = "A new title"
    run.save()

    mock_deadline_sync_task.assert_not_called()


def test_resaving_same_deadline_does_not_queue_edx_sync(mock_deadline_sync_task):
    """Re-assigning the identical deadline is not a change."""
    run = CourseRunFactory.create()
    mock_deadline_sync_task.reset_mock()

    run.upgrade_deadline = run.upgrade_deadline
    run.save()

    mock_deadline_sync_task.assert_not_called()


def test_new_run_with_deadline_queues_edx_sync(mock_deadline_sync_task):
    """A run created with a deadline should push it."""
    run = CourseRunFactory.create(upgrade_deadline=now_in_utc() + timedelta(days=10))

    mock_deadline_sync_task.assert_called_once_with(run.id)


def test_new_run_without_deadline_does_not_queue_edx_sync(mock_deadline_sync_task):
    """Creating a run with no deadline has nothing to push."""
    CourseRunFactory.create(upgrade_deadline=None)

    mock_deadline_sync_task.assert_not_called()


def test_clearing_deadline_queues_edx_sync(mock_deadline_sync_task):
    """
    Clearing the deadline still queues, so the task can report that edX's copy
    cannot be unset through the API and needs a manual fix.
    """
    run = CourseRunFactory.create(upgrade_deadline=now_in_utc() + timedelta(days=10))
    mock_deadline_sync_task.reset_mock()

    run.upgrade_deadline = None
    run.save()

    mock_deadline_sync_task.assert_called_once_with(run.id)


def test_deferred_deadline_does_not_queue_edx_sync(mock_deadline_sync_task):
    """
    A run loaded with upgrade_deadline deferred should be left alone - touching
    the attribute would trigger a refetch and we have nothing to compare.
    """
    run = CourseRunFactory.create()
    mock_deadline_sync_task.reset_mock()

    deferred_run = CourseRun.objects.defer("upgrade_deadline").get(id=run.id)
    deferred_run.title = "Retitled without loading the deadline"
    deferred_run.save()

    mock_deadline_sync_task.assert_not_called()
