"""Tests for courses admin views"""

import pytest
from django.contrib import admin as django_admin
from django.urls import reverse

from courses.admin import CourseRunEnrollmentAdmin
from courses.factories import (
    CourseRunEnrollmentFactory,
    PartnerSchoolFactory,
    PartnerSchoolProgramFactory,
    ProgramFactory,
)
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
