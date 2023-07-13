"""
Tests for signals
"""
from datetime import timedelta
from unittest.mock import patch

import pytest
from mitol.common.utils import now_in_utc

from courses.factories import (
    CourseFactory,
    CourseRunCertificateFactory,
    CourseRunFactory,
    ProgramFactory,
    UserFactory,
)
from main import settings

pytestmark = pytest.mark.django_db


# pylint: disable=unused-argument
@patch("courses.signals.transaction.on_commit", side_effect=lambda callback: callback())
@patch("courses.signals.generate_multiple_programs_certificate", autospec=True)
def test_create_course_certificate(generate_program_cert_mock, mock_on_commit):
    """
    Test that generate_multiple_programs_certificate is called when a course
    certificate is created
    """
    user = UserFactory.create()
    course_run = CourseRunFactory.create()
    program = ProgramFactory.create()
    program.add_requirement(course_run.course)
    cert = CourseRunCertificateFactory.create(user=user, course_run=course_run)
    generate_program_cert_mock.assert_called_once_with(user, [program])
    cert.save()
    generate_program_cert_mock.assert_called_once_with(user, [program])


# pylint: disable=unused-argument
@patch("courses.signals.transaction.on_commit", side_effect=lambda callback: callback())
@patch("courses.signals.generate_multiple_programs_certificate", autospec=True)
def test_generate_program_certificate_not_called(
    generate_program_cert_mock, mock_on_commit
):
    """
    Test that generate_multiple_programs_certificate is not called when a course
    is not associated with program.
    """
    user = UserFactory.create()
    course = CourseFactory.create()
    course_run = CourseRunFactory.create(course=course)
    cert = CourseRunCertificateFactory.create(user=user, course_run=course_run)
    cert.save()
    generate_program_cert_mock.assert_not_called()


# pylint: disable=unused-argument
@patch("courses.signals.transaction.on_commit", side_effect=lambda callback: callback())
@patch("courses.signals.generate_course_run_certificates_for_course", autospec=True)
@pytest.mark.parametrize("certificates_date_past", [True, False])
def test_courserun_post_update_signal(
    generate_course_run_cert_mock, mock_on_commit, certificates_date_past
):
    """
    Test that generate_course_run_certificates_for_course is not called when
    certificate_available_date is in the future
    """
    course = CourseFactory.create()
    now = now_in_utc()
    delta = timedelta(hours=settings.CERTIFICATE_CREATION_DELAY_IN_HOURS)
    course_run = CourseRunFactory.create(
        course=course,
        certificate_available_date=now - delta
        if certificates_date_past
        else now + delta,
    )
    course_run.save()
    if certificates_date_past:
        generate_course_run_cert_mock.assert_called_once()
    else:
        generate_course_run_cert_mock.assert_not_called()
