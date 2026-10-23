# ruff: noqa: PLC0415
"""
Tasks for the courses app
"""

import logging

from django.db.models import Q
from mitol.common.utils.datetime import now_in_utc
from requests.exceptions import HTTPError, RequestException

from courses.models import (
    CourseRun,
    CourseRunEnrollment,
    LearnerProgramRecordShare,
)
from main.celery import app

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
    # RequestException covers connection errors and timeouts. Permanent 4xx
    # errors are caught in the task and never reach autoretry.
    autoretry_for=(RequestException,),
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
        str | None: the UpgradeDeadlineSyncResult value, for log/flower
            visibility, or None when the run is gone or edX rejected the push.
    """
    from openedx.api import sync_courserun_upgrade_deadline_to_edx

    run = CourseRun.all_objects.filter(id=course_run_id).first()
    if run is None:
        log.warning(
            "CourseRun %s no longer exists, skipping upgrade deadline sync",
            course_run_id,
        )
        return None

    try:
        return str(sync_courserun_upgrade_deadline_to_edx(run))
    except HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        if status_code is None or status_code == 429 or status_code >= 500:  # noqa: PLR2004
            # Rate limited or an edX outage: autoretry_for retries these.
            raise
        # The rest won't succeed on retry. Keep edX's response body: it carries
        # the validation message that str(exc) leaves out.
        body = exc.response.text[:500]
        if status_code in (401, 403):
            # A credentials problem affects every run, not just this one.
            log.error(  # noqa: TRY400
                "edX rejected the service worker token (status %s) while pushing "
                "the upgrade deadline for %s: %s",
                status_code,
                run.courseware_id,
                body,
            )
        else:
            log.exception(
                "edX rejected the upgrade deadline push for %s (status %s): %s",
                run.courseware_id,
                status_code,
                body,
            )
        return None


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
