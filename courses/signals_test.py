"""
Tests for signals
"""

from unittest.mock import patch

import pytest

from courses.factories import (
    CourseFactory,
    CourseRunCertificateFactory,
    CourseRunFactory,
    ProgramFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db


# pylint: disable=unused-argument
@patch("courses.signals.transaction.on_commit", side_effect=lambda callback: callback())
@patch("courses.signals.generate_multiple_programs_certificate", autospec=True)
def test_create_course_certificate(generate_program_cert_mock, mock_on_commit, mocker):
    """
    Test that generate_multiple_programs_certificate is called when a course
    certificate is created
    """
    mocker.patch(
        "hubspot_sync.management.commands.configure_hubspot_properties._upsert_custom_properties",
    )
    user = UserFactory.create()
    course_run = CourseRunFactory.create()
    program = ProgramFactory.create()
    program.add_requirement(course_run.course)
    cert = CourseRunCertificateFactory.create(user=user, course_run=course_run)
    generate_program_cert_mock.assert_called_once_with(user, [program])
    cert.save()
    generate_program_cert_mock.assert_called_once_with(user, [program])


@patch("courses.signals.transaction.on_commit", side_effect=lambda callback: callback())
@patch("courses.signals.generate_multiple_programs_certificate", autospec=True)
def test_generate_program_certificate_if_not_live(
    generate_program_cert_mock, mock_on_commit, mocker
):
    """
    Test that generate_multiple_programs_certificate is not called when a program is not live
    """
    mocker.patch(
        "hubspot_sync.management.commands.configure_hubspot_properties._upsert_custom_properties",
    )
    user = UserFactory.create()
    course_run = CourseRunFactory.create()
    program = ProgramFactory.create(live=False)
    program.add_requirement(course_run.course)
    cert = CourseRunCertificateFactory.create(user=user, course_run=course_run)
    generate_program_cert_mock.assert_not_called()
    cert.save()
    generate_program_cert_mock.assert_not_called()


# pylint: disable=unused-argument
@patch("courses.signals.transaction.on_commit", side_effect=lambda callback: callback())
@patch("courses.signals.generate_multiple_programs_certificate", autospec=True)
def test_generate_program_certificate_not_called(
    generate_program_cert_mock, mock_on_commit, mocker
):
    """
    Test that generate_multiple_programs_certificate is not called when a course
    is not associated with program.
    """
    mocker.patch(
        "hubspot_sync.management.commands.configure_hubspot_properties._upsert_custom_properties",
    )
    user = UserFactory.create()
    course = CourseFactory.create()
    course_run = CourseRunFactory.create(course=course)
    cert = CourseRunCertificateFactory.create(user=user, course_run=course_run)
    cert.save()
    generate_program_cert_mock.assert_not_called()
