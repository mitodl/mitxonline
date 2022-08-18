"""
Tasks for the courses app
"""
import logging
from datetime import timedelta

from django.conf import settings
from django.db.models import Q

from courses.models import CourseRun, CourseRunEnrollment, CourseRunCertificate
from courses.utils import exception_logging_generator
from openedx.api import get_edx_grades_with_users

from mitol.common.utils.datetime import now_in_utc
from main.celery import app

log = logging.getLogger(__name__)


@app.task
def sync_courseruns_data():
    """
    Task to sync titles and dates for course runs from edX.
    """
    from courses.api import sync_course_runs

    now = now_in_utc()
    runs = CourseRun.objects.live().filter(
        Q(expiration_date__isnull=True) | Q(expiration_date__gt=now)
    )

    # `sync_course_runs` logs internally so no need to capture/output the returned values
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
    now = now_in_utc()
    # Get all the course runs valid course runs for certificates/Grades
    # For a valid run it would be live,
    # .. end_date would be in future with addition of delay settings.CERTIFICATE_CREATION_DELAY_IN_HOURS

    course_runs = CourseRun.objects.live().filter(
        Q(end_date__isnull=True)
        | Q(
            end_date__gt=now
            - timedelta(hours=settings.CERTIFICATE_CREATION_DELAY_IN_HOURS)
        )
    )
    if course_runs is None or course_runs.count() == 0:
        log.info("No course runs matched the certificates generation criteria")
        return

    # Inline to fix the circular dependency
    from courses.api import (
        process_course_run_grade_certificate,
        ensure_course_run_grade,
    )

    for run in course_runs:
        edx_grade_user_iter = exception_logging_generator(
            get_edx_grades_with_users(run)
        )
        created_grades_count, updated_grades_count, generated_certificates_count = (
            0,
            0,
            0,
        )
        for edx_grade, user in edx_grade_user_iter:
            course_run_grade, created, updated = ensure_course_run_grade(
                user=user, course_run=run, edx_grade=edx_grade, should_update=True
            )

            if created:
                created_grades_count += 1
            elif updated:
                updated_grades_count += 1

            # Check certificate generation eligibility
            #   1. For self_paced course runs we generate certificates right away irrespective of end_date
            #   2. For others course runs we generate the certificates if the end of course run has passed
            if run.self_paced_certificates or (run.end_date <= now):
                _, created, deleted = process_course_run_grade_certificate(
                    course_run_grade=course_run_grade
                )

                if deleted:
                    log.warning(
                        "Certificate deleted for user %s and course_run %s", user, run
                    )
                elif created:
                    log.warning(
                        "Certificate created for user %s and course_run %s", user, run
                    )
                    generated_certificates_count += 1
        log.info(
            f"Finished processing course run {run}: created grades for {created_grades_count} users, updated grades for {updated_grades_count} users, generated certificates for {generated_certificates_count} users"
        )
