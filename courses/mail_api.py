"""Ecommerce mail API"""

import logging

from mitol.mail.api import get_message_sender

from courses.messages import (
    CourseRunEnrollmentMessage,
    CourseRunUnenrollmentMessage,
    EnrollmentFailureMessage,
    PartnerSchoolSharingMessage,
)
from courses.models import CourseRun
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
        with get_message_sender(PartnerSchoolSharingMessage) as sender:
            sender.build_and_send_message(
                learner_record.partner_school.email,
                {
                    "learner_record": learner_record,
                    "record_link": f"{SITE_BASE_URL}/records/shared/{learner_record.share_uuid}",
                },
            )
    except Exception:  # pylint: disable=broad-except
        log.exception("Error sending partner school sharing email")
