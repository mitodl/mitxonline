"""
Tasks for the courses app
"""

from django.db.models import Q
from mitol.common.utils.datetime import now_in_utc

from courses.models import CourseRun, CourseRunEnrollment
from main.celery import app


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
