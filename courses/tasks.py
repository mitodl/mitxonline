# ruff: noqa: PLC0415
"""
Tasks for the courses app
"""

import logging

from django.db.models import Q
from mitol.common.utils.datetime import now_in_utc

from courses.models import (
    CourseRun,
    CourseRunEnrollment,
    LearnerProgramRecordShare,
)
from main.celery import app
from users.models import User

log = logging.getLogger(__name__)


@app.task
def sync_courseruns_data():
    """
    Task to sync titles and dates for course runs from edX.
    """
    from courses.api import sync_course_mode, sync_course_runs

    now = now_in_utc()
    runs = (
        CourseRun.objects.live(include_b2b=True)
        .filter(Q(expiration_date__isnull=True) | Q(expiration_date__gt=now))
        .exclude(run_tag__startswith="fake-")
    )

    # `sync_course_runs` logs internally so no need to capture/output the returned values
    sync_course_mode(runs)
    sync_course_runs(runs)


@app.task(acks_late=True)
def subscribe_edx_course_emails(enrollment_id):
    """Task to subscribe user to edX Emails"""
    from openedx.api import subscribe_to_edx_course_emails

    enrollment = CourseRunEnrollment.objects.select_related("user", "run").get(
        id=enrollment_id
    )

    subscribed = subscribe_to_edx_course_emails(enrollment.user, enrollment.run)

    if subscribed:
        enrollment.edx_emails_subscription = subscribed
        enrollment.save()


@app.task
def generate_course_certificates(force=False, username=None, courseware_id=None):  # noqa: FBT002
    """
    Task to generate certificates for courses.
    """
    from courses.api import generate_course_run_certificates

    user = None
    if username is not None:
        try:
            user = User.objects.get(edx_username=username)
        except User.DoesNotExist:
            log.info(f"User with username {username} does not exist.")  # noqa: G004
            return
    generate_course_run_certificates(
        force=force, user=user, courseware_id=courseware_id
    )


@app.task
def send_partner_school_email(record_uuid):
    """
    Task to send the partner school emails.
    """
    from courses.mail_api import send_partner_school_sharing_message

    record = LearnerProgramRecordShare.objects.get(share_uuid=record_uuid)

    send_partner_school_sharing_message(record)
