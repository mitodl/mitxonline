"""Tests for Course related tasks"""

import pytest

from courses.factories import CourseRunEnrollmentFactory
from courses.tasks import subscribe_edx_course_emails

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
