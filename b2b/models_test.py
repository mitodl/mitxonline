"""Tests for models."""

import faker
import pytest

from b2b.factories import ContractPageFactory
from courses.factories import CourseRunFactory, ProgramFactory

pytestmark = [pytest.mark.django_db]
FAKE = faker.Faker()


def test_add_program_courses_to_contract(mocker):
    """Test that adding a program to a contract works as expected."""

    mocker.patch("openedx.tasks.clone_courserun.delay")

    program = ProgramFactory.create()
    courseruns = CourseRunFactory.create_batch(3)
    contract = ContractPageFactory.create()

    for courserun in courseruns:
        program.add_requirement(courserun.course)

    program.refresh_from_db()

    created, skipped = contract.add_program_courses(program)

    assert created == 3
    assert skipped == 0

    contract.save()
    contract.refresh_from_db()

    assert contract.programs.count() == 1
    assert contract.get_course_runs().count() == 3

    new_courserun = CourseRunFactory.create()
    program.add_requirement(new_courserun.course)
    program.save()
    program.refresh_from_db()

    created, skipped = contract.add_program_courses(program)

    assert created == 1
    assert skipped == 3

    contract.save()
    contract.refresh_from_db()

    assert contract.programs.count() == 1
    assert contract.get_course_runs().count() == 4
