"""Tests for Course related tasks"""

import pytest
from celery.exceptions import Retry
from requests import Response
from requests.exceptions import HTTPError, ReadTimeout

from courses.factories import (
    CourseRunEnrollmentFactory,
    CourseRunFactory,
    LearnerProgramRecordShareFactory,
)
from courses.tasks import (
    downgrade_enrollments,
    generate_course_certificates,
    generate_program_certificates,
    send_partner_school_email,
    subscribe_edx_course_emails,
    sync_courserun_upgrade_deadline,
)
from openedx.constants import (
    EDX_ENROLLMENT_AUDIT_MODE,
    EDX_ENROLLMENT_VERIFIED_MODE,
    UpgradeDeadlineSyncResult,
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


def _http_error(status_code, body=b""):
    """Build an HTTPError carrying a response with the given status."""
    response = Response()
    response.status_code = status_code
    response._content = body  # noqa: SLF001
    return HTTPError(response=response)


@pytest.mark.parametrize(
    "error",
    [_http_error(429), _http_error(500), _http_error(503), HTTPError("no response")],
)
def test_sync_courserun_upgrade_deadline_retries_transient_errors(mocker, error):
    """Rate limiting, edX outages and errors without a response are retried."""
    run = CourseRunFactory.create()
    sync_patch = mocker.patch(
        "openedx.api.sync_courserun_upgrade_deadline_to_edx",
        side_effect=error,
    )

    with pytest.raises(Retry):
        sync_courserun_upgrade_deadline.delay(run.id)

    sync_patch.assert_called_once_with(run)


@pytest.mark.parametrize("status_code", [400, 404])
def test_sync_courserun_upgrade_deadline_does_not_retry_client_errors(
    mocker, caplog, status_code
):
    """
    Other 4xx errors won't succeed on retry, so they're logged once, with the
    status and edX's response body.
    """
    run = CourseRunFactory.create()
    sync_patch = mocker.patch(
        "openedx.api.sync_courserun_upgrade_deadline_to_edx",
        side_effect=_http_error(status_code, b'{"expiration_datetime": ["bad"]}'),
    )

    result = sync_courserun_upgrade_deadline.delay(run.id)

    assert result.get() is None
    sync_patch.assert_called_once_with(run)
    assert f"edX rejected the upgrade deadline push for {run.courseware_id}" in (
        caplog.text
    )
    assert f"status {status_code}" in caplog.text
    assert '{"expiration_datetime": ["bad"]}' in caplog.text


@pytest.mark.parametrize("status_code", [401, 403])
def test_sync_courserun_upgrade_deadline_reports_auth_errors(
    mocker, caplog, status_code
):
    """
    A rejected service token is a credentials problem, not a problem with this
    run, so it gets its own message and isn't retried.
    """
    run = CourseRunFactory.create()
    mocker.patch(
        "openedx.api.sync_courserun_upgrade_deadline_to_edx",
        side_effect=_http_error(status_code),
    )

    result = sync_courserun_upgrade_deadline.delay(run.id)

    assert result.get() is None
    assert "edX rejected the service worker token" in caplog.text
    assert "edX rejected the upgrade deadline push" not in caplog.text


def test_sync_courserun_upgrade_deadline_retries_read_timeouts(mocker):
    """A slow edX response is retried like other transient failures."""
    run = CourseRunFactory.create()
    mocker.patch(
        "openedx.api.sync_courserun_upgrade_deadline_to_edx",
        side_effect=ReadTimeout(),
    )

    with pytest.raises(Retry):
        sync_courserun_upgrade_deadline.delay(run.id)


def test_downgrade_enrollments(mocker):
    """
    Active verified enrollments are downgraded in edX and locally; inactive and
    audit ones are skipped, and an edX failure doesn't stop the rest.
    """
    patched_edx_enroll = mocker.patch("courses.api.enroll_in_edx_course_runs")
    mocker.patch("courses.api.mail_api")
    verified = CourseRunEnrollmentFactory.create(
        enrollment_mode=EDX_ENROLLMENT_VERIFIED_MODE
    )
    edx_failure = CourseRunEnrollmentFactory.create(
        enrollment_mode=EDX_ENROLLMENT_VERIFIED_MODE, edx_enrollment_retry_count=99
    )
    inactive = CourseRunEnrollmentFactory.create(
        enrollment_mode=EDX_ENROLLMENT_VERIFIED_MODE, active=False
    )
    audit = CourseRunEnrollmentFactory.create(enrollment_mode=EDX_ENROLLMENT_AUDIT_MODE)

    def fail_for_one_user(user, runs, mode):
        if user == edx_failure.user:
            raise HTTPError

    patched_edx_enroll.side_effect = fail_for_one_user

    downgrade_enrollments.delay(
        [e.id for e in (verified, edx_failure, inactive, audit)]
    )

    assert patched_edx_enroll.call_count == 2
    verified.refresh_from_db()
    assert verified.enrollment_mode == EDX_ENROLLMENT_AUDIT_MODE
    # edX failed: audit locally, flagged for the repair job with fresh retries
    edx_failure.refresh_from_db()
    assert edx_failure.enrollment_mode == EDX_ENROLLMENT_AUDIT_MODE
    assert edx_failure.edx_enrolled is False
    assert edx_failure.edx_enrollment_retry_count == 0
    inactive.refresh_from_db()
    assert inactive.active is False
    assert inactive.enrollment_mode == EDX_ENROLLMENT_VERIFIED_MODE


def test_downgrade_enrollments_logs_local_failure(mocker):
    """A failed local downgrade is logged as a failure even if edX succeeded"""
    mocker.patch("courses.api.downgrade_learner", return_value=([], True))
    mock_log = mocker.patch("courses.tasks.log")
    enrollment = CourseRunEnrollmentFactory.create(
        enrollment_mode=EDX_ENROLLMENT_VERIFIED_MODE
    )

    downgrade_enrollments.delay([enrollment.id])

    mock_log.error.assert_called_once_with(
        "Failed to downgrade enrollment(s) %s", [enrollment.id]
    )
