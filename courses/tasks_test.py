"""Tests for Course related tasks"""

import pytest

from courses.factories import (
    CourseRunEnrollmentFactory,
    LearnerProgramRecordShareFactory,
    ProgramEnrollmentFactory,
)
from courses.tasks import (
    generate_course_certificates,
    send_partner_school_email,
    subscribe_edx_course_emails,
    upgrade_eligible_program_enrollments,
)
from openedx.constants import EDX_ENROLLMENT_AUDIT_MODE, EDX_ENROLLMENT_VERIFIED_MODE

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


def test_upgrade_eligible_program_enrollments_selects_related_program_and_user(
    mocker,
    django_assert_max_num_queries,
):
    """The task should not issue per-enrollment queries for user or program."""
    audit_enrollments = ProgramEnrollmentFactory.create_batch(
        3,
        enrollment_mode=EDX_ENROLLMENT_AUDIT_MODE,
    )
    ProgramEnrollmentFactory.create(enrollment_mode=EDX_ENROLLMENT_VERIFIED_MODE)

    def mock_upgrade(program_enrollment):
        program_enrollment.program.title
        program_enrollment.user.username
        return program_enrollment, False

    upgrade_program_enrollment_if_eligible = mocker.patch(
        "courses.api.upgrade_program_enrollment_if_eligible",
        side_effect=mock_upgrade,
    )

    with django_assert_max_num_queries(1):
        upgrade_eligible_program_enrollments()

    assert upgrade_program_enrollment_if_eligible.call_count == len(audit_enrollments)


