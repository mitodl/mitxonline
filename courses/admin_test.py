"""Tests for courses admin views"""

import pytest
from django.contrib import admin as django_admin
from django.urls import reverse
from requests.exceptions import HTTPError

from courses.admin import CourseRunEnrollmentAdmin
from courses.api import (
    VERIFIABLE_CREDENTIAL_STATUS_DISABLED,
    VERIFIABLE_CREDENTIAL_STATUS_DISABLED_NO_CRITERIA,
    VERIFIABLE_CREDENTIAL_STATUS_ENABLED,
    VERIFIABLE_CREDENTIAL_STATUS_NO_CRITERIA,
)
from courses.factories import (
    CourseRunEnrollmentFactory,
    CourseRunFactory,
    PartnerSchoolFactory,
    PartnerSchoolProgramFactory,
    ProgramFactory,
)
from courses.models import CourseRunEnrollment
from main.features import IGNORE_EDX_FAILURES
from openedx.constants import (
    EDX_ENROLLMENT_AUDIT_MODE,
    EDX_ENROLLMENT_VERIFIED_MODE,
    OPENEDX_ENROLLMENT_REPAIR_MAX_RETRIES,
)
from users.factories import UserFactory

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


def test_partner_school_admin_change_page_lists_program_inline(admin_client):
    """The change page exposes the program assignment inline, including alt_email."""
    school = PartnerSchoolFactory.create()
    program = ProgramFactory.create(title="Supply Chain Management")
    PartnerSchoolProgramFactory.create(partner_school=school, program=program)

    resp = admin_client.get(
        reverse("admin:courses_partnerschool_change", args=[school.id])
    )

    assert resp.status_code == 200
    assert b"program_links" in resp.content
    assert b"alt_email" in resp.content


def test_partner_school_admin_changelist_filters_by_program(admin_client):
    """The changelist can be filtered down to one program's schools."""
    scm = ProgramFactory.create()
    dedp = ProgramFactory.create()
    scm_school = PartnerSchoolFactory.create(name="SCM Only School")
    dedp_school = PartnerSchoolFactory.create(name="DEDP Only School")
    PartnerSchoolProgramFactory.create(partner_school=scm_school, program=scm)
    PartnerSchoolProgramFactory.create(partner_school=dedp_school, program=dedp)

    resp = admin_client.get(
        reverse("admin:courses_partnerschool_changelist"),
        {"programs__id__exact": scm.id},
    )

    assert resp.status_code == 200
    assert b"SCM Only School" in resp.content
    assert b"DEDP Only School" not in resp.content

def test_verifiable_credential_stats_view(mocker, admin_client):
    """The stats page should render the certificate page status breakdown"""
    page = mocker.Mock(id=123)
    page.title = "Some Certificate"
    mock_summary = mocker.patch(
        "courses.admin.summarize_verifiable_credential_certificate_statuses",
        return_value={VERIFIABLE_CREDENTIAL_STATUS_NO_CRITERIA: [page]},
    )

    resp = admin_client.get(reverse("admin:courses_verifiablecredential_stats"))

    assert resp.status_code == 200
    mock_summary.assert_called_once_with(return_objects=True)
    rows = {row["status"]: row["pages"] for row in resp.context["stats"]}
    assert rows == {
        VERIFIABLE_CREDENTIAL_STATUS_ENABLED: [],
        VERIFIABLE_CREDENTIAL_STATUS_NO_CRITERIA: [page],
        VERIFIABLE_CREDENTIAL_STATUS_DISABLED: [],
        VERIFIABLE_CREDENTIAL_STATUS_DISABLED_NO_CRITERIA: [],
    }
    assert "Some Certificate" in resp.content.decode()


def test_verifiable_credential_stats_view_requires_staff(client, user):
    """Non-staff users should not be able to see the stats page"""
    client.force_login(user)
    resp = client.get(reverse("admin:courses_verifiablecredential_stats"))
    assert resp.status_code == 302

ENROLL_IN_RUNS_URL = "admin:courses_courserunenrollment_enroll_in_runs"


def test_enroll_in_runs_lists_only_matching_runs(admin_client):
    """The enroll page should only offer runs whose courseware_id ends in 0T2026"""
    matching = CourseRunFactory.create(courseware_id="course-v1:MITx+X1+0T2026")
    other = CourseRunFactory.create(courseware_id="course-v1:MITx+X1+1T2026")

    response = admin_client.get(reverse(ENROLL_IN_RUNS_URL))

    assert response.status_code == 200
    run_ids = set(
        response.context["form"].fields["runs"].queryset.values_list("id", flat=True)
    )
    assert matching.id in run_ids
    assert other.id not in run_ids


@pytest.mark.parametrize("lookup", ["email", "username", "id"])
def test_enroll_in_runs_enrolls_user_in_selected_runs(mocker, admin_client, lookup):
    """Posting the form should enroll the user in each selected run individually"""
    user = UserFactory.create()
    run_a = CourseRunFactory.create(courseware_id="course-v1:MITx+A+0T2026")
    run_b = CourseRunFactory.create(courseware_id="course-v1:MITx+B+0T2026")
    CourseRunFactory.create(courseware_id="course-v1:MITx+C+0T2026")
    mock_enroll = mocker.patch(
        "courses.admin.create_run_enrollments", return_value=([mocker.Mock()], True)
    )

    response = admin_client.post(
        reverse(ENROLL_IN_RUNS_URL),
        {
            "user": str(getattr(user, lookup)),
            "runs": [run_a.id, run_b.id],
        },
    )

    assert response.status_code == 302
    assert mock_enroll.call_count == 2
    mock_enroll.assert_any_call(user, [run_a], mode=EDX_ENROLLMENT_AUDIT_MODE)
    mock_enroll.assert_any_call(user, [run_b], mode=EDX_ENROLLMENT_AUDIT_MODE)


def test_enroll_in_runs_ignores_requested_mode(mocker, admin_client):
    """The form has no mode choice, so a posted verified mode is ignored"""
    user = UserFactory.create()
    run = CourseRunFactory.create(courseware_id="course-v1:MITx+A+0T2026")
    mock_enroll = mocker.patch(
        "courses.admin.create_run_enrollments", return_value=([mocker.Mock()], True)
    )

    admin_client.post(
        reverse(ENROLL_IN_RUNS_URL),
        {"user": user.email, "runs": [run.id], "mode": EDX_ENROLLMENT_VERIFIED_MODE},
    )

    mock_enroll.assert_called_once_with(user, [run], mode=EDX_ENROLLMENT_AUDIT_MODE)


def test_enroll_in_runs_continues_after_failure(mocker, admin_client):
    """A failure in one run should be reported without blocking the others"""
    user = UserFactory.create()
    run_a = CourseRunFactory.create(courseware_id="course-v1:MITx+A+0T2026")
    run_b = CourseRunFactory.create(courseware_id="course-v1:MITx+B+0T2026")
    mock_enroll = mocker.patch(
        "courses.admin.create_run_enrollments",
        side_effect=[Exception("boom"), ([mocker.Mock()], True)],
    )

    response = admin_client.post(
        reverse(ENROLL_IN_RUNS_URL),
        {"user": user.email, "runs": [run_a.id, run_b.id]},
        follow=True,
    )

    assert mock_enroll.call_count == 2
    message_texts = [str(m) for m in response.context["messages"]]
    assert any("boom" in text for text in message_texts)
    assert any(
        f"Enrolled {user.email} in {run_b.courseware_id}" in t for t in message_texts
    )


def test_enroll_in_runs_unknown_user(mocker, admin_client):
    """An unknown user should re-render the form with an error and not enroll"""
    run = CourseRunFactory.create(courseware_id="course-v1:MITx+A+0T2026")
    mock_enroll = mocker.patch("courses.admin.create_run_enrollments")

    response = admin_client.post(
        reverse(ENROLL_IN_RUNS_URL),
        {"user": "nobody@example.com", "runs": [run.id]},
    )

    assert response.status_code == 200
    assert "user" in response.context["form"].errors
    mock_enroll.assert_not_called()


def test_enroll_in_runs_enrolls_in_edx(mocker, admin_client):
    """The enroll page should create the enrollment in Open edX as well as locally"""
    mocker.patch("courses.api.mail_api")
    mocker.patch("courses.api.subscribe_edx_course_emails")
    mock_edx_enroll = mocker.patch("courses.api.enroll_in_edx_course_runs")
    user = UserFactory.create()
    run = CourseRunFactory.create(courseware_id="course-v1:MITx+A+0T2026")

    admin_client.post(
        reverse(ENROLL_IN_RUNS_URL),
        {"user": user.email, "runs": [run.id]},
    )

    mock_edx_enroll.assert_called_once_with(user, [run], mode=EDX_ENROLLMENT_AUDIT_MODE)
    enrollment = CourseRunEnrollment.objects.get(user=user, run=run)
    assert enrollment.edx_enrolled is True
    assert enrollment.enrollment_mode == EDX_ENROLLMENT_AUDIT_MODE


def test_enroll_in_runs_reports_edx_failure(mocker, admin_client, settings):
    """An edX failure should be reported and leave no local enrollment behind"""
    settings.FEATURES[IGNORE_EDX_FAILURES] = False
    mocker.patch("courses.api.mail_api")
    mocker.patch(
        "courses.api.enroll_in_edx_course_runs",
        side_effect=HTTPError("edX is down"),
    )
    user = UserFactory.create()
    run = CourseRunFactory.create(courseware_id="course-v1:MITx+A+0T2026")

    response = admin_client.post(
        reverse(ENROLL_IN_RUNS_URL),
        {"user": user.email, "runs": [run.id]},
        follow=True,
    )

    message_texts = [str(m) for m in response.context["messages"]]
    assert any("edX enrollment failed" in text for text in message_texts)
    assert not CourseRunEnrollment.all_objects.filter(user=user, run=run).exists()

