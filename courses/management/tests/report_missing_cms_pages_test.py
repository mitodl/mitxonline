"""Tests for report_missing_cms_pages command."""

from io import StringIO

import pytest

from cms.models import CertificatePage
from courses.factories import (
    CourseFactory,
    CourseRunEnrollmentFactory,
    CourseRunFactory,
    CourseRunGradeFactory,
    ProgramEnrollmentFactory,
    ProgramFactory,
)
from courses.management.commands import report_missing_cms_pages
from openedx.constants import EDX_ENROLLMENT_AUDIT_MODE, EDX_ENROLLMENT_VERIFIED_MODE

pytestmark = [pytest.mark.django_db]


def _run_command(**kwargs):
    out = StringIO()
    command = report_missing_cms_pages.Command(stdout=out)
    command.handle(**kwargs)
    return out.getvalue()


def test_report_missing_cms_pages_all_buckets():
    """The command should report all missing-page bucket counts correctly."""
    # Healthy records
    CourseFactory.create()
    ProgramFactory.create()

    # Missing course page
    CourseFactory.create(page=None)

    # Missing course certificate page
    course_missing_cert_page = CourseFactory.create()
    CertificatePage.objects.descendant_of(course_missing_cert_page.page).delete()

    # Missing program page
    ProgramFactory.create(page=None)

    # Missing program certificate page
    program_missing_cert_page = ProgramFactory.create()
    CertificatePage.objects.descendant_of(program_missing_cert_page.page).delete()

    output = _run_command()

    assert "Courses missing CMS page: 1" in output
    assert "Courses missing CMS certificate page: 1" in output
    assert "Programs missing CMS page: 1" in output
    assert "Programs missing CMS certificate page: 1" in output


def test_report_missing_cms_pages_live_filter():
    """The --live filter should only include live courseware."""
    live_course = CourseFactory.create(page=None, live=True)
    non_live_course = CourseFactory.create(page=None, live=False)
    live_program = ProgramFactory.create(page=None, live=True)
    non_live_program = ProgramFactory.create(page=None, live=False)

    output = _run_command(live=True)

    assert "Courses missing CMS page: 1" in output
    assert "Programs missing CMS page: 1" in output
    assert live_course.live is True
    assert non_live_course.live is False
    assert live_program.live is True
    assert non_live_program.live is False


def test_report_missing_cms_pages_eligible_users_only_filter():
    """The --eligible-users-only filter should include only cert-eligible courseware."""
    eligible_course = CourseFactory.create(page=None)
    eligible_run = CourseRunFactory.create(course=eligible_course)
    eligible_enrollment = CourseRunEnrollmentFactory.create(
        run=eligible_run,
        enrollment_mode=EDX_ENROLLMENT_VERIFIED_MODE,
    )
    CourseRunGradeFactory.create(
        course_run=eligible_run,
        user=eligible_enrollment.user,
        passed=True,
        grade=0.9,
    )

    # Not eligible due to no paid enrollment
    ineligible_course = CourseFactory.create(page=None)
    ineligible_run = CourseRunFactory.create(course=ineligible_course)
    ineligible_enrollment = CourseRunEnrollmentFactory.create(
        run=ineligible_run,
        enrollment_mode=EDX_ENROLLMENT_AUDIT_MODE,
    )
    CourseRunGradeFactory.create(
        course_run=ineligible_run,
        user=ineligible_enrollment.user,
        passed=True,
        grade=0.9,
    )

    eligible_program = ProgramFactory.create(page=None, live=True)
    ProgramEnrollmentFactory.create(
        program=eligible_program,
        enrollment_mode=EDX_ENROLLMENT_VERIFIED_MODE,
        active=True,
    )

    ineligible_program = ProgramFactory.create(page=None, live=True)
    ProgramEnrollmentFactory.create(
        program=ineligible_program,
        enrollment_mode=EDX_ENROLLMENT_AUDIT_MODE,
        active=True,
    )

    output = _run_command(eligible_users_only=True)

    assert "Courses missing CMS page: 1" in output
    assert "Programs missing CMS page: 1" in output
