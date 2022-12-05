"""Course mail API tests"""
import pytest
from django.urls import reverse
from mitol.common.factories import UserFactory
from pytz import UTC

from courses.factories import (
    CourseRunEnrollmentFactory,
    CourseRunFactory,
    LearnerProgramRecordShareFactory,
    ProgramFactory,
)
from courses.mail_api import (
    send_course_run_enrollment_email,
    send_enrollment_failure_message,
    send_partner_school_sharing_message,
)
from courses.messages import (
    CourseRunEnrollmentMessage,
    EnrollmentFailureMessage,
    PartnerSchoolSharingMessage,
)
from main.settings import SITE_BASE_URL

pytestmark = pytest.mark.django_db


def test_send_course_run_enrollment_email(mocker):
    """send_course_run_enrollment_email should send an email for the given enrollment"""
    patched_get_message_sender = mocker.patch("courses.mail_api.get_message_sender")
    mock_sender = patched_get_message_sender.return_value.__enter__.return_value
    enrollment = CourseRunEnrollmentFactory.create()

    send_course_run_enrollment_email(enrollment)

    patched_get_message_sender.assert_called_once_with(CourseRunEnrollmentMessage)
    mock_sender.build_and_send_message.assert_called_once_with(
        enrollment.user, {"enrollment": enrollment}
    )


def test_send_course_run_enrollment_email_error(mocker):
    """send_course_run_enrollment_email handle and log errors"""
    patched_get_message_sender = mocker.patch("courses.mail_api.get_message_sender")
    mock_sender = patched_get_message_sender.return_value.__enter__.return_value
    patched_log = mocker.patch("courses.mail_api.log")
    mock_sender.build_and_send_message.side_effect = Exception("error")
    enrollment = CourseRunEnrollmentFactory.create()

    send_course_run_enrollment_email(enrollment)

    patched_log.exception.assert_called_once_with(
        "Error sending enrollment success email"
    )


@pytest.mark.parametrize("is_program", [True, False])
def test_send_enrollment_failure_message(user, mocker, is_program):
    """Test that send_enrollment_failure_message sends a message with proper formatting"""
    patched_get_message_sender = mocker.patch("courses.mail_api.get_message_sender")
    mock_sender = patched_get_message_sender.return_value.__enter__.return_value
    enrollment_obj = (
        ProgramFactory.create() if is_program else CourseRunFactory.create()
    )
    details = "TestException on line 21"

    send_enrollment_failure_message(user, enrollment_obj, details)
    patched_get_message_sender.assert_called_once_with(EnrollmentFailureMessage)
    mock_sender.build_and_send_message.assert_called_once_with(
        user,
        {
            "enrollment_type": "Program" if is_program else "Run",
            "enrollment_obj": enrollment_obj,
            "details": details,
        },
    )


def test_send_partner_school_sharing_message(mocker):
    """Test that the partner school message goes to the right spot"""
    record = LearnerProgramRecordShareFactory()
    record_link = SITE_BASE_URL + reverse(
        "shared_learner_record_from_uuid", kwargs={"uuid": record.share_uuid}
    )

    patched_get_message_sender = mocker.patch("courses.mail_api.get_message_sender")
    mock_sender = patched_get_message_sender.return_value.__enter__.return_value

    send_partner_school_sharing_message(record)
    patched_get_message_sender.assert_called_once_with(PartnerSchoolSharingMessage)
    mock_sender.build_and_send_message.assert_called_once_with(
        record.partner_school.email,
        {"learner_record": record, "record_link": record_link},
    )
