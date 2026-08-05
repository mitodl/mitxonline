# ruff: noqa: PLC0415
"""
Tasks for the courses app
"""

import logging

from django.db.models import Prefetch, Q
from mitol.common.utils.datetime import now_in_utc
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import HTTPError

from courses.models import (
    CourseRun,
    CourseRunEnrollment,
    LearnerProgramRecordShare,
    ProgramEnrollment,
    ProgramRequirement,
)
from main.celery import app
from openedx.constants import EDX_ENROLLMENT_AUDIT_MODE

log = logging.getLogger(__name__)


@app.task
def sync_courseruns_data():
    """
    Task to sync titles and dates for course runs from edX.
    """
    from courses.api import sync_course_runs

    now = now_in_utc()
    runs = (
        CourseRun.objects.live(include_b2b=True)
        .filter(Q(expiration_date__isnull=True) | Q(expiration_date__gt=now))
        .exclude(run_tag__startswith="fake-")
    )

    # `sync_course_runs` logs internally so no need to capture/output the returned values
    sync_course_runs(runs)


@app.task(
    autoretry_for=(HTTPError, RequestsConnectionError),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def sync_courserun_upgrade_deadline(course_run_id):
    """
    Push a single course run's upgrade deadline into its edX verified mode.

    Queued from the CourseRun post_save signal, so it must tolerate the run
    having been deleted between the save and the task running.

    Args:
        course_run_id (int): pk of the CourseRun to sync.

    Returns:
        str: the UpgradeDeadlineSyncResult value, for log/flower visibility.
    """
    from openedx.api import sync_courserun_upgrade_deadline_to_edx

    run = CourseRun.all_objects.filter(id=course_run_id).first()
    if run is None:
        log.warning(
            "CourseRun %s no longer exists, skipping upgrade deadline sync",
            course_run_id,
        )
        return None

    return str(sync_courserun_upgrade_deadline_to_edx(run))


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
def generate_program_certificates(batch_size=500):
    """
    Task to create program certificates for verified enrollments that have
    earned them but were not issued a certificate (e.g. due to a missed signal).

    Args:
        batch_size (int): Number of enrollments to process per pk-windowed batch.
    """
    from courses.api import (
        generate_missing_program_certificates as _api_fn,
    )

    results = _api_fn(batch_size=batch_size)
    log.info(
        "generate_program_certificates task finished: %s",
        results,
    )


@app.task
def upgrade_eligible_program_enrollments():
    """Upgrade eligible learners for all audit-mode program enrollments."""
    from courses.api import upgrade_program_enrollment_if_eligible

    enrollments = (
        ProgramEnrollment.objects.filter(enrollment_mode=EDX_ENROLLMENT_AUDIT_MODE)
        .select_related("program", "user")
        .prefetch("certificate")
        .prefetch_related(
            Prefetch(
                "program__all_requirements",
                queryset=ProgramRequirement.objects.select_related("course"),
            )
        )
    )
    for enrollment in enrollments:
        upgrade_program_enrollment_if_eligible(enrollment)
