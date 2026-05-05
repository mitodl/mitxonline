"""Tests for Course related tasks"""

import pytest

from courses.factories import (
    CourseRunEnrollmentFactory,
    LearnerProgramRecordShareFactory,
)
from courses.tasks import (
    generate_course_certificates,
    generate_missing_program_certificates,
    send_partner_school_email,
    subscribe_edx_course_emails,
)

pytestmark = pytest.mark.django_db


def test_subscribe_edx_course_emails(mocker, user):
    """Test that subscribe_edx_course_emails task updates the state correctly after subscribing to edX emails"""
    enrollment = CourseRunEnrollmentFactory.create(
        user=user, edx_enrolled=True, active=True, edx_emails_subscription=False
    )
    subscribe_edx_emails_patch = mocker.patch(
        "openedx.api.subscribe_to_edx_course_emails", return_value=True
    )

    subscribe_edx_course_emails.delay(enrollment_id=enrollment.id)

    subscribe_edx_emails_patch.assert_called_once()
    enrollment.refresh_from_db()
    assert enrollment.edx_emails_subscription is True


def test_generate_course_certificates_task(mocker):
    """Test generate_course_certificates calls the right api functionality from courses"""

    generate_course_run_certificates = mocker.patch(
        "courses.api.generate_course_run_certificates"
    )
    generate_course_certificates.delay()
    generate_course_run_certificates.assert_called_once()


def test_send_partner_school_email(mocker):
    """Test generate_course_certificates calls the right api functionality from courses"""
    record = LearnerProgramRecordShareFactory()

    send_partner_school_sharing_message = mocker.patch(
        "courses.mail_api.send_partner_school_sharing_message"
    )
    send_partner_school_email.delay(record.share_uuid)
    send_partner_school_sharing_message.assert_called_once()


def test_generate_missing_program_certificates_task_dry_run(mocker):
    """Task delegates to the API function with dry_run=True by default."""
    mock_api = mocker.patch(
        "courses.api.generate_missing_program_certificates",
        return_value={
            "processed": 0,
            "would_create": 0,
            "created": 0,
            "ineligible": 0,
            "failed": 0,
        },
    )
    generate_missing_program_certificates.delay()
    mock_api.assert_called_once_with(dry_run=True, batch_size=500)


def test_generate_missing_program_certificates_task_write_mode(mocker):
    """Task delegates to the API function with dry_run=False when requested."""
    mock_api = mocker.patch(
        "courses.api.generate_missing_program_certificates",
        return_value={
            "processed": 1,
            "would_create": 0,
            "created": 1,
            "ineligible": 0,
            "failed": 0,
        },
    )
    generate_missing_program_certificates.delay(dry_run=False)
    mock_api.assert_called_once_with(dry_run=False, batch_size=500)
