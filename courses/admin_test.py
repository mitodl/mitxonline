"""Tests for courses admin views"""

from datetime import timedelta

import pytest
from django.contrib import admin as django_admin
from django.urls import reverse
from mitol.common.utils.datetime import now_in_utc
from requests.exceptions import HTTPError

from courses.admin import CourseRunAdmin, CourseRunEnrollmentAdmin
from courses.api import (
    VERIFIABLE_CREDENTIAL_STATUS_DISABLED,
    VERIFIABLE_CREDENTIAL_STATUS_DISABLED_NO_CRITERIA,
    VERIFIABLE_CREDENTIAL_STATUS_ENABLED,
    VERIFIABLE_CREDENTIAL_STATUS_NO_CRITERIA,
)
from courses.factories import (
    CourseFactory,
    CourseRunEnrollmentFactory,
    CourseRunFactory,
    PartnerSchoolFactory,
    PartnerSchoolProgramFactory,
    ProgramFactory,
)
from courses.models import CourseRun, CourseRunEnrollment
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


def _courserun_admin_save(client, run, **overrides):
    """
    Build the POST payload the CourseRun admin change form expects.

    The inline management forms are read off the change page so that the payload
    keeps validating as inlines are added to CourseRunAdmin.
    """
    change_page = client.get(reverse("admin:courses_courserun_change", args=(run.id,)))
    data = {
        field.html_name: field.value()
        for inline in change_page.context["inline_admin_formsets"]
        for field in inline.formset.management_form
    }
    data |= {
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
            client, run, upgrade_deadline_0="2030-06-01", upgrade_deadline_1="00:00:00"
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
        _courserun_admin_save(client, run),
        follow=True,
    )

    assert response.status_code == 200
    run.refresh_from_db()
    assert run.upgrade_deadline is None
    assert any(
        "Clear it by hand in the edX Django admin" in message
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
            client,
            run,
            title="A different title",
            upgrade_deadline_0=deadline.strftime("%Y-%m-%d"),
            upgrade_deadline_1=deadline.strftime("%H:%M:%S"),
        ),
        follow=True,
    )

    assert response.status_code == 200
    run.refresh_from_db()
    assert run.title == "A different title"
    assert not any(
        "upgrade deadline" in message.lower() for message in _admin_messages(response)
    )


@pytest.mark.parametrize("has_deadline", [True, False])
def test_courserun_admin_add_warns_deadline_not_pushed(
    rf, admin_user, mocker, has_deadline
):
    """
    Adding a run doesn't push its deadline (new runs are skipped), so the admin
    warns that edX keeps its own date, and never claims a sync was queued.
    """
    mocker.patch("courses.signals.transaction.on_commit")
    mock_messages = mocker.patch("courses.admin.messages")
    run = CourseRunFactory.build(
        course=CourseFactory.create(),
        upgrade_deadline=now_in_utc() + timedelta(days=10) if has_deadline else None,
    )
    request = rf.post("/")
    request.user = admin_user
    form = mocker.Mock(changed_data=["upgrade_deadline"] if has_deadline else [])

    CourseRunAdmin(CourseRun, django_admin.site).save_model(
        request, run, form, change=False
    )

    assert run.pk is not None
    mock_messages.info.assert_not_called()
    if has_deadline:
        mock_messages.warning.assert_called_once()
        assert "New runs aren't pushed to edX" in mock_messages.warning.call_args[0][1]
    else:
        mock_messages.warning.assert_not_called()


def test_courserun_admin_push_upgrade_deadline_action(rf, admin_user, mocker):
    """
    The action queues a push for each selected run with a deadline, even when
    the deadline hasn't changed, and skips runs without one.
    """
    mock_push = mocker.patch("courses.tasks.sync_courserun_upgrade_deadline.delay")
    mock_messages = mocker.patch("courses.admin.messages")
    with_deadline = CourseRunFactory.create(
        upgrade_deadline=now_in_utc() + timedelta(days=10)
    )
    without_deadline = CourseRunFactory.create(upgrade_deadline=None)
    request = rf.post("/")
    request.user = admin_user

    CourseRunAdmin(CourseRun, django_admin.site).push_upgrade_deadline_to_edx(
        request,
        CourseRun.all_objects.filter(id__in=[with_deadline.id, without_deadline.id]),
    )

    mock_push.assert_called_once_with(with_deadline.id)
    message = mock_messages.info.call_args[0][1]
    assert "Queued an upgrade deadline push to edX for 1 run(s)" in message
    assert "Skipped 1 run(s) with no upgrade deadline" in message


def test_courserun_admin_add_warning_points_to_push_action(rf, admin_user, mocker):
    """The add warning tells staff how to push the deadline they just entered."""
    mocker.patch("courses.signals.transaction.on_commit")
    mock_messages = mocker.patch("courses.admin.messages")
    run = CourseRunFactory.build(
        course=CourseFactory.create(),
        upgrade_deadline=now_in_utc() + timedelta(days=10),
    )
    request = rf.post("/")
    request.user = admin_user

    CourseRunAdmin(CourseRun, django_admin.site).save_model(
        request, run, mocker.Mock(changed_data=["upgrade_deadline"]), change=False
    )

    message = mock_messages.warning.call_args[0][1]
    assert '"Push upgrade deadline to edX"' in message
    assert "change the deadline here" not in message


@pytest.mark.parametrize("edx_success", [True, False])
def test_undo_program_entitlement_verification_action(
    mocker, admin_client, edx_success
):
    """The undo action reports each enrollment's outcome without stopping on errors"""
    undone = CourseRunEnrollmentFactory.create()
    refused = CourseRunEnrollmentFactory.create()
    order = mocker.Mock(reference_number="mitxonline-test-1")
    mock_undo = mocker.patch(
        "courses.admin.undo_program_course_run_verification",
        side_effect=lambda enrollment: (
            ([order], edx_success)
            if enrollment == undone
            else (_ for _ in ()).throw(ValueError("not verified"))
        ),
    )

    response = admin_client.post(
        reverse("admin:courses_courserunenrollment_changelist"),
        {
            "action": "undo_program_entitlement_verification",
            "_selected_action": [str(undone.id), str(refused.id)],
        },
        follow=True,
    )

    assert mock_undo.call_count == 2
    message_texts = [str(m) for m in response.context["messages"]]
    assert "Skipped: not verified" in message_texts
    undone_message = next(t for t in message_texts if undone.user.email in t)
    assert "mitxonline-test-1" in undone_message
    assert ("edX downgrade failed" in undone_message) is not edx_success


def test_undo_program_entitlement_verification_action_inactive(mocker, admin_client):
    """An inactive enrollment is reported as downgraded locally and left inactive"""
    enrollment = CourseRunEnrollmentFactory.create(active=False)
    mocker.patch(
        "courses.admin.undo_program_course_run_verification",
        return_value=([mocker.Mock(reference_number="mitxonline-test-2")], True),
    )

    response = admin_client.post(
        reverse("admin:courses_courserunenrollment_changelist"),
        {
            "action": "undo_program_entitlement_verification",
            "_selected_action": [str(enrollment.id)],
        },
        follow=True,
    )

    message_texts = [str(m) for m in response.context["messages"]]
    assert any("left inactive" in t and "mitxonline-test-2" in t for t in message_texts)
