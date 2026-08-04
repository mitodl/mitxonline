"""Tests for courses admin views"""

from datetime import timedelta

import pytest
from django.contrib import admin as django_admin
from django.urls import reverse
from mitol.common.utils.datetime import now_in_utc

from courses.admin import CourseRunEnrollmentAdmin
from courses.factories import CourseRunEnrollmentFactory, CourseRunFactory
from courses.models import CourseRunEnrollment
from openedx.constants import OPENEDX_ENROLLMENT_REPAIR_MAX_RETRIES

pytestmark = [pytest.mark.django_db]


def test_reset_edx_enrollment_retry_count_action(client, admin_user):
    """The reset action should zero out the retry count for selected enrollments"""
    client.force_login(admin_user)
    exhausted = CourseRunEnrollmentFactory.create(
        edx_enrolled=False,
        edx_enrollment_retry_count=OPENEDX_ENROLLMENT_REPAIR_MAX_RETRIES,
    )
    untouched = CourseRunEnrollmentFactory.create(
        edx_enrolled=False,
        edx_enrollment_retry_count=OPENEDX_ENROLLMENT_REPAIR_MAX_RETRIES,
    )

    response = client.post(
        reverse("admin:courses_courserunenrollment_changelist"),
        {
            "action": "reset_edx_enrollment_retry_count",
            "_selected_action": [str(exhausted.id)],
        },
        follow=True,
    )

    assert response.status_code == 200
    exhausted.refresh_from_db()
    untouched.refresh_from_db()
    assert exhausted.edx_enrollment_retry_count == 0
    assert untouched.edx_enrollment_retry_count == OPENEDX_ENROLLMENT_REPAIR_MAX_RETRIES


@pytest.mark.parametrize(
    "edx_enrolled,retry_count,expected",  # noqa: PT006
    [
        (False, OPENEDX_ENROLLMENT_REPAIR_MAX_RETRIES, True),
        (False, OPENEDX_ENROLLMENT_REPAIR_MAX_RETRIES - 1, False),
        (True, OPENEDX_ENROLLMENT_REPAIR_MAX_RETRIES, False),
    ],
)
def test_repair_exhausted_display(edx_enrolled, retry_count, expected):
    """repair_exhausted should reflect the same threshold retry_failed_edx_enrollments uses"""
    enrollment = CourseRunEnrollmentFactory.build(
        edx_enrolled=edx_enrolled, edx_enrollment_retry_count=retry_count
    )
    admin_instance = CourseRunEnrollmentAdmin(CourseRunEnrollment, django_admin.site)

    assert admin_instance.repair_exhausted(enrollment) is expected


def _courserun_admin_save(run, **overrides):
    """Build the POST payload the CourseRun admin change form expects."""
    data = {
        "title": run.title,
        "course": str(run.course_id),
        "courseware_id": run.courseware_id,
        "run_tag": run.run_tag,
        "language": run.language or "en",
        "variant_industry": run.variant_industry or "",
        "variant_length": run.variant_length or "",
        "start_date_0": "",
        "start_date_1": "",
        "end_date_0": "",
        "end_date_1": "",
        "enrollment_start_0": "",
        "enrollment_start_1": "",
        "enrollment_end_0": "",
        "enrollment_end_1": "",
        "expiration_date_0": "",
        "expiration_date_1": "",
        "certificate_available_date_0": "",
        "certificate_available_date_1": "",
        "upgrade_deadline_0": "",
        "upgrade_deadline_1": "",
        "_save": "Save",
    }
    data.update(overrides)
    return data


def _admin_messages(response):
    """Collect message strings out of a followed admin response."""
    return [str(message) for message in response.context["messages"]]


def test_courserun_admin_reports_queued_deadline_sync(client, admin_user, mocker):
    """
    Saving a new deadline in the admin should tell the operator that the push to
    edX was queued.
    """
    mocker.patch("courses.signals.transaction.on_commit")
    run = CourseRunFactory.create(upgrade_deadline=None)
    client.force_login(admin_user)

    response = client.post(
        reverse("admin:courses_courserun_change", args=(run.id,)),
        _courserun_admin_save(
            run, upgrade_deadline_0="2030-06-01", upgrade_deadline_1="00:00:00"
        ),
        follow=True,
    )

    assert response.status_code == 200
    run.refresh_from_db()
    assert run.upgrade_deadline is not None
    assert any(
        "push the upgrade deadline" in message and run.courseware_id in message
        for message in _admin_messages(response)
    )


def test_courserun_admin_warns_that_clearing_cannot_reach_edx(
    client, admin_user, mocker
):
    """
    Clearing the deadline cannot be propagated (edX's API cannot unset an
    existing expiration date), so the admin has to say so - a celery log warning
    would never be seen by the person making the change.
    """
    mocker.patch("courses.signals.transaction.on_commit")
    run = CourseRunFactory.create(upgrade_deadline=now_in_utc() + timedelta(days=10))
    client.force_login(admin_user)

    response = client.post(
        reverse("admin:courses_courserun_change", args=(run.id,)),
        _courserun_admin_save(run),
        follow=True,
    )

    assert response.status_code == 200
    run.refresh_from_db()
    assert run.upgrade_deadline is None
    assert any(
        "must clear it by hand in the edX Django admin" in message
        for message in _admin_messages(response)
    )


def test_courserun_admin_silent_when_deadline_untouched(client, admin_user, mocker):
    """An unrelated admin edit should not emit deadline messaging."""
    mocker.patch("courses.signals.transaction.on_commit")
    deadline = now_in_utc() + timedelta(days=10)
    run = CourseRunFactory.create(upgrade_deadline=deadline)
    client.force_login(admin_user)

    response = client.post(
        reverse("admin:courses_courserun_change", args=(run.id,)),
        _courserun_admin_save(
            run,
            title="A different title",
            upgrade_deadline_0=deadline.strftime("%Y-%m-%d"),
            upgrade_deadline_1=deadline.strftime("%H:%M:%S"),
        ),
        follow=True,
    )

    assert response.status_code == 200
    assert not any(
        "upgrade deadline" in message.lower() for message in _admin_messages(response)
    )
