"""Tests for the backfill_b2b_program_enrollments command."""

import pytest
from django.core.management import call_command

from b2b.constants import CONTRACT_MEMBERSHIP_MANAGED
from b2b.factories import ContractPageFactory
from b2b.models import ContractProgramItem
from courses.factories import (
    CourseFactory,
    CourseRunEnrollmentFactory,
    CourseRunFactory,
    ProgramFactory,
)
from courses.models import ProgramEnrollment

pytestmark = [pytest.mark.django_db]

COMMAND = "backfill_b2b_program_enrollments"


def _setup_b2b_enrollment(*, add_course_to_program=True, link_contract_program=True):
    """Create a user enrolled in a B2B course run, plus a contract program.

    Returns (enrollment, program).
    """

    contract = ContractPageFactory.create(
        membership_type=CONTRACT_MEMBERSHIP_MANAGED,
    )
    program = ProgramFactory.create()
    course = CourseFactory.create()

    if add_course_to_program:
        program.add_requirement(course)

    if link_contract_program:
        ContractProgramItem.objects.create(
            contract=contract, program=program, sort_order=0
        )

    run = CourseRunFactory.create(course=course, b2b_contract=contract)
    enrollment = CourseRunEnrollmentFactory.create(run=run)

    return enrollment, program


def test_backfill_creates_missing_program_enrollment():
    """An unambiguous B2B enrollment should get a ProgramEnrollment on commit."""

    enrollment, program = _setup_b2b_enrollment()

    call_command(COMMAND, "--commit")

    assert ProgramEnrollment.objects.filter(
        user=enrollment.user, program=program
    ).exists()


def test_backfill_dry_run_creates_nothing():
    """Without --commit, no ProgramEnrollment should be created."""

    enrollment, program = _setup_b2b_enrollment()

    call_command(COMMAND)

    assert not ProgramEnrollment.objects.filter(
        user=enrollment.user, program=program
    ).exists()


def test_backfill_is_idempotent():
    """Running twice should not error or duplicate enrollments."""

    enrollment, program = _setup_b2b_enrollment()

    call_command(COMMAND, "--commit")
    call_command(COMMAND, "--commit")

    assert (
        ProgramEnrollment.all_objects.filter(
            user=enrollment.user, program=program
        ).count()
        == 1
    )


def test_backfill_skips_ambiguous_course():
    """A course in 2+ contract programs should be skipped, not enrolled."""

    contract = ContractPageFactory.create(
        membership_type=CONTRACT_MEMBERSHIP_MANAGED,
    )
    course = CourseFactory.create()
    program_a = ProgramFactory.create()
    program_b = ProgramFactory.create()

    for program in (program_a, program_b):
        program.add_requirement(course)
        ContractProgramItem.objects.create(
            contract=contract, program=program, sort_order=0
        )

    run = CourseRunFactory.create(course=course, b2b_contract=contract)
    enrollment = CourseRunEnrollmentFactory.create(run=run)

    call_command(COMMAND, "--commit")

    assert not ProgramEnrollment.objects.filter(user=enrollment.user).exists()


def test_backfill_skips_course_not_in_any_program():
    """A B2B enrollment whose course maps to no contract program is skipped."""

    enrollment, program = _setup_b2b_enrollment(link_contract_program=False)

    call_command(COMMAND, "--commit")

    assert not ProgramEnrollment.objects.filter(user=enrollment.user).exists()


def test_backfill_ignores_non_b2b_enrollments():
    """Enrollments in runs without a B2B contract are untouched."""

    program = ProgramFactory.create()
    course = CourseFactory.create()
    program.add_requirement(course)
    run = CourseRunFactory.create(course=course, b2b_contract=None)
    enrollment = CourseRunEnrollmentFactory.create(run=run)

    call_command(COMMAND, "--commit")

    assert not ProgramEnrollment.objects.filter(user=enrollment.user).exists()
