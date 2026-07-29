"""Course mail API tests"""

import pytest

from courses.factories import (
    CourseRunEnrollmentFactory,
    CourseRunFactory,
    LearnerProgramRecordShareFactory,
    PartnerSchoolProgramFactory,
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
from main import features
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


def test_send_partner_school_sharing_message(mocker, settings):
    """The record goes to the per-program recipient address."""
    settings.FEATURES[features.ENABLE_PROGRAM_SPECIFIC_PATHWAY_SCHOOLS] = True
    record = LearnerProgramRecordShareFactory()
    PartnerSchoolProgramFactory.create(
        partner_school=record.partner_school,
        program=record.program,
        email="scm@example.com",
    )
    record_link = f"{SITE_BASE_URL}/records/shared/{record.share_uuid}"

    patched_get_message_sender = mocker.patch("courses.mail_api.get_message_sender")
    mock_sender = patched_get_message_sender.return_value.__enter__.return_value

    send_partner_school_sharing_message(record)

    patched_get_message_sender.assert_called_once_with(PartnerSchoolSharingMessage)
    mock_sender.build_and_send_message.assert_called_once_with(
        "scm@example.com",
        {"learner_record": record, "record_link": record_link},
    )


def test_send_partner_school_sharing_message_all_recipients(mocker, settings):
    """A school with two recipients for the program gets one message each."""
    settings.FEATURES[features.ENABLE_PROGRAM_SPECIFIC_PATHWAY_SCHOOLS] = True
    record = LearnerProgramRecordShareFactory()
    for email in ["vd@example.com", "cs@example.com"]:
        PartnerSchoolProgramFactory.create(
            partner_school=record.partner_school,
            program=record.program,
            email=email,
        )
    record_link = f"{SITE_BASE_URL}/records/shared/{record.share_uuid}"

    patched_get_message_sender = mocker.patch("courses.mail_api.get_message_sender")
    mock_sender = patched_get_message_sender.return_value.__enter__.return_value

    send_partner_school_sharing_message(record)

    context = {"learner_record": record, "record_link": record_link}
    assert mock_sender.build_and_send_message.call_count == 2
    mock_sender.build_and_send_message.assert_any_call("vd@example.com", context)
    mock_sender.build_and_send_message.assert_any_call("cs@example.com", context)


def test_send_partner_school_sharing_message_never_sends_to_alt_email(mocker, settings):
    """alt_email is reference data only and must never receive a record."""
    settings.FEATURES[features.ENABLE_PROGRAM_SPECIFIC_PATHWAY_SCHOOLS] = True
    record = LearnerProgramRecordShareFactory()
    PartnerSchoolProgramFactory.create(
        partner_school=record.partner_school,
        program=record.program,
        email="primary@example.com",
        alt_email="alternative@example.com",
    )

    patched_get_message_sender = mocker.patch("courses.mail_api.get_message_sender")
    mock_sender = patched_get_message_sender.return_value.__enter__.return_value

    send_partner_school_sharing_message(record)

    recipients = [
        call.args[0] for call in mock_sender.build_and_send_message.call_args_list
    ]
    assert recipients == ["primary@example.com"]
    assert "alternative@example.com" not in recipients


def test_send_partner_school_sharing_message_falls_back_to_school_email(
    mocker, settings
):
    """With no per-program address the school's own email is used."""
    settings.FEATURES[features.ENABLE_PROGRAM_SPECIFIC_PATHWAY_SCHOOLS] = True
    record = LearnerProgramRecordShareFactory()
    record_link = f"{SITE_BASE_URL}/records/shared/{record.share_uuid}"

    patched_get_message_sender = mocker.patch("courses.mail_api.get_message_sender")
    mock_sender = patched_get_message_sender.return_value.__enter__.return_value

    send_partner_school_sharing_message(record)

    mock_sender.build_and_send_message.assert_called_once_with(
        record.partner_school.email,
        {"learner_record": record, "record_link": record_link},
    )


def test_send_partner_school_sharing_message_flag_off_ignores_program_links(
    mocker, settings
):
    """With the flag off, mail goes to the school's own address even when
    per-program links exist. This is the guarantee that entering assignments
    cannot change delivery before the flag is flipped.
    """
    settings.FEATURES[features.ENABLE_PROGRAM_SPECIFIC_PATHWAY_SCHOOLS] = False
    record = LearnerProgramRecordShareFactory()
    record.partner_school.email = "generic@example.com"
    record.partner_school.save()
    PartnerSchoolProgramFactory.create(
        partner_school=record.partner_school,
        program=record.program,
        email="dept@example.com",
    )
    record_link = f"{SITE_BASE_URL}/records/shared/{record.share_uuid}"

    patched_get_message_sender = mocker.patch("courses.mail_api.get_message_sender")
    mock_sender = patched_get_message_sender.return_value.__enter__.return_value

    send_partner_school_sharing_message(record)

    mock_sender.build_and_send_message.assert_called_once_with(
        "generic@example.com",
        {"learner_record": record, "record_link": record_link},
    )


def test_send_partner_school_sharing_message_flag_off_single_recipient(
    mocker, settings
):
    """With the flag off, two program links still produce exactly one message."""
    settings.FEATURES[features.ENABLE_PROGRAM_SPECIFIC_PATHWAY_SCHOOLS] = False
    record = LearnerProgramRecordShareFactory()
    record.partner_school.email = "generic@example.com"
    record.partner_school.save()
    for email in ["vd@example.com", "cs@example.com"]:
        PartnerSchoolProgramFactory.create(
            partner_school=record.partner_school, program=record.program, email=email
        )

    patched_get_message_sender = mocker.patch("courses.mail_api.get_message_sender")
    mock_sender = patched_get_message_sender.return_value.__enter__.return_value

    send_partner_school_sharing_message(record)

    recipients = [
        call.args[0] for call in mock_sender.build_and_send_message.call_args_list
    ]
    assert recipients == ["generic@example.com"]
