"""Tests for Course related tasks"""

import pytest

from courses.factories import (
    CourseRunEnrollmentFactory,
    CourseRunFactory,
    LearnerProgramRecordShareFactory,
)
from courses.tasks import (
    generate_course_certificates,
    generate_program_certificates,
    send_partner_school_email,
    subscribe_edx_course_emails,
    sync_courserun_upgrade_deadline,
)
from openedx.constants import UpgradeDeadlineSyncResult

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


def test_generate_program_certificates_task(mocker):
    """Task delegates to the API function."""
    mock_api = mocker.patch(
        "courses.api.generate_missing_program_certificates",
        return_value={
            "processed": 1,
            "created": 1,
            "ineligible": 0,
            "failed": 0,
        },
    )
    generate_program_certificates.delay()
    mock_api.assert_called_once_with(batch_size=500)


def test_sync_courserun_upgrade_deadline(mocker):
    """The task should hand the resolved run to the edX sync function."""
    run = CourseRunFactory.create()
    sync_patch = mocker.patch(
        "openedx.api.sync_courserun_upgrade_deadline_to_edx",
        return_value=UpgradeDeadlineSyncResult.UPDATED,
    )

    result = sync_courserun_upgrade_deadline.delay(run.id)

    sync_patch.assert_called_once_with(run)
    assert result.get() == UpgradeDeadlineSyncResult.UPDATED.value


def test_sync_courserun_upgrade_deadline_missing_run(mocker):
    """
    A run deleted between the save and the task running should be skipped, not
    raise - the task is queued from post_save via on_commit.
    """
    sync_patch = mocker.patch("openedx.api.sync_courserun_upgrade_deadline_to_edx")

    result = sync_courserun_upgrade_deadline.delay(-1)

    sync_patch.assert_not_called()
    assert result.get() is None


def test_sync_courserun_upgrade_deadline_finds_source_runs(mocker):
    """
    The task must use all_objects: B2B/source runs are excluded from the default
    manager, and their deadlines still need to reach edX.
    """
    run = CourseRunFactory.create(is_source_run=True)
    sync_patch = mocker.patch(
        "openedx.api.sync_courserun_upgrade_deadline_to_edx",
        return_value=UpgradeDeadlineSyncResult.UPDATED,
    )

    sync_courserun_upgrade_deadline.delay(run.id)

    sync_patch.assert_called_once_with(run)
