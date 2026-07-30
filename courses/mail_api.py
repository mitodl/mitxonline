"""Ecommerce mail API"""

import logging

from mitol.mail.api import get_message_sender
from mitol.olposthog.features import is_enabled

from courses.messages import (
    CourseRunEnrollmentMessage,
    CourseRunUnenrollmentMessage,
    EnrollmentFailureMessage,
    PartnerSchoolSharingMessage,
)
from courses.models import CourseRun
from main import features
from main.settings import SITE_BASE_URL

log = logging.getLogger()


def send_course_run_enrollment_email(enrollment):
    """
    Notify the user of successful enrollment for a course run

    Args:
        enrollment (CourseRunEnrollment): the enrollment for which to send the email
    """
    try:
        user = enrollment.user

        with get_message_sender(CourseRunEnrollmentMessage) as sender:
            sender.build_and_send_message(user, {"enrollment": enrollment})
    except Exception:  # pylint: disable=broad-except
        log.exception("Error sending enrollment success email")


def send_course_run_unenrollment_email(enrollment):
    """
    Notify the user of successful unenrollment for a course run

    Args:
        enrollment (CourseRunEnrollment): the enrollment for which to send the email
    """
    try:
        user = enrollment.user

        with get_message_sender(CourseRunUnenrollmentMessage) as sender:
            sender.build_and_send_message(user, {"enrollment": enrollment})
    except Exception:  # pylint: disable=broad-except
        log.exception("Error sending unenrollment success email")


def send_enrollment_failure_message(user, enrollment_obj, details):
    """
    Args:
        user (User): the user for a failed enrollment
        enrollment_obj (Program or CourseRun): the object that failed enrollment
        details (str): Details of the error (typically a stack trace)
    """
    try:
        with get_message_sender(EnrollmentFailureMessage) as sender:
            sender.build_and_send_message(
                user,
                {
                    "enrollment_type": (
                        "Run" if isinstance(enrollment_obj, CourseRun) else "Program"
                    ),
                    "enrollment_obj": enrollment_obj,
                    "details": details,
                },
            )
    except Exception:  # pylint: disable=broad-except
        log.exception("Error sending unenrollment success email")


def send_partner_school_sharing_message(learner_record):
    """
    Args:
        learner_record (LearnerProgramRecordShare): the learner record to send
    """
    try:
        # Second of two deliberate flag reads for hq#12321 (the other is
        # courses.api.partner_schools_for_program). Gating mail here keeps the
        # flag's promise: entering program assignments cannot change delivery
        # until the flag is flipped, so data-entry mistakes stay harmless.
        if is_enabled(features.ENABLE_PROGRAM_SPECIFIC_PATHWAY_SCHOOLS):
            recipients = learner_record.partner_school.emails_for_program(
                learner_record.program
            )
        else:
            recipients = [learner_record.partner_school.email]
        context = {
            "learner_record": learner_record,
            "record_link": f"{SITE_BASE_URL}/records/shared/{learner_record.share_uuid}",
        }
        with get_message_sender(PartnerSchoolSharingMessage) as sender:
            for recipient in recipients:
                try:
                    sender.build_and_send_message(recipient, context)
                except Exception:  # pylint: disable=broad-except  # noqa: PERF203
                    log.exception(
                        "Error sending partner school sharing email to %s for share %s",
                        recipient,
                        learner_record.share_uuid,
                    )
    except Exception:  # pylint: disable=broad-except
        log.exception("Error sending partner school sharing email")
