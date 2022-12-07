"""
Tasks for the courses app
"""
import logging

from django.conf import settings
from django.db.models import Q
from mitol.common.utils.datetime import now_in_utc

from courses.models import (
    CourseRun,
    CourseRunEnrollment,
    LearnerProgramRecordShare,
    Program,
)
from main.celery import app

log = logging.getLogger(__name__)


@app.task
def sync_courseruns_data():
    """
    Task to sync titles and dates for course runs from edX.
    """
    from courses.api import sync_course_mode, sync_course_runs

    now = now_in_utc()
    runs = CourseRun.objects.live().filter(
        Q(expiration_date__isnull=True) | Q(expiration_date__gt=now)
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
def generate_course_certificates():
    """
    Task to generate certificates for courses.
    """
    from courses.api import generate_course_run_certificates

    generate_course_run_certificates()


@app.task
def send_partner_school_email(record_uuid):
    """
    Task to send the partner school emails.
    """
    from courses.mail_api import send_partner_school_sharing_message

    record = LearnerProgramRecordShare.objects.get(share_uuid=record_uuid)

    send_partner_school_sharing_message(record)


@app.task
def check_for_program_orphans():
    """
    Check the programs for orphaned courses. You can do something similar to
    this by using the check_program_requirements management command. This just
    lets the API call run; it'll throw errors if it finds things.

    This only checks Live programs; if they're not Live then they're unlikely to
    cause issues in the front-end.
    """
    from courses.api import check_program_for_orphans

    for program in Program.objects.filter(live=True).all():
        log.info(f"check_for_program_orphans: checking program {program.readable_id}")
        check_program_for_orphans(program)
