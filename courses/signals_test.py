"""
Tests for signals
"""

from unittest.mock import patch

import pytest

from courses.factories import (
    CourseFactory,
    CourseRunCertificateFactory,
    CourseRunFactory,
    ProgramCertificateFactory,
    ProgramFactory,
    UserFactory,
)

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
