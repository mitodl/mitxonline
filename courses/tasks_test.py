"""Tests for Course related tasks"""

from datetime import timedelta

import pytest
from mitol.common.utils.datetime import now_in_utc

from courses.factories import (
    CourseRunEnrollmentFactory,
    CourseRunFactory,
    CourseRunGradeFactory,
    LearnerProgramRecordShareFactory,
)
from courses.models import CourseRunEnrollment, PaidCourseRun
from courses.tasks import (
    clear_unenrolled_paid_course_run,
    generate_course_certificates,
    send_partner_school_email,
    subscribe_edx_course_emails,
)
from ecommerce.factories import OrderFactory
from ecommerce.models import Order
from openedx.constants import EDX_ENROLLMENT_VERIFIED_MODE

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


def test_clear_unenrolled_paid_course_runs(user):
    """Test generating a paid course run, then clearing the enrollment"""

    course_run = CourseRunFactory.create()
    enrollment = CourseRunEnrollment.objects.create(user=user, run=course_run)
    order = OrderFactory.create(purchaser=user, state=Order.STATE.FULFILLED)

    PaidCourseRun.objects.create(user=user, course_run=course_run, order=order)

    clear_unenrolled_paid_course_run(enrollment.id)

    assert (
        PaidCourseRun.objects.filter(
            user=user, course_run=course_run, order=order
        ).count()
        == 0
    )
