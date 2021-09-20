"""
Tasks for the courses app
"""

from django.db.models import Q
from mitol.common.utils.datetime import now_in_utc

from courses.api import sync_course_runs
from courses.models import CourseRun
from main.celery import app


@app.task
def sync_course_runs_data():
    """
    Task to sync titles and dates for course runs from edX.
    """
    now = now_in_utc()
    runs = CourseRun.objects.live().filter(
        Q(expiration_date__isnull=True) | Q(expiration_date__gt=now)
    )

    # `sync_course_runs` logs internally so no need to capture/output the returned values
    sync_course_runs(runs)
