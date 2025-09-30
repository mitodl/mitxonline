"""Shared pytest configuration for courses application"""

import random

import pytest

from courses.factories import (
    CourseFactory,
    CourseRunFactory,
    ProgramFactory,
    ProgramRequirementFactory,
)
from courses.models import (
    ProgramRequirement,
    ProgramRequirementNodeType,
)


@pytest.fixture
def programs():
    """Fixture for a set of Programs in the database"""
    return ProgramFactory.create_batch(3)


@pytest.fixture
def courses():
    """Fixture for a set of Courses in the database"""
    return CourseFactory.create_batch(3)


@pytest.fixture
def course_runs():
    """Fixture for a set of CourseRuns in the database"""
    return CourseRunFactory.create_batch(3)


@pytest.fixture
def course_catalog_program_count(request):
    return getattr(request, "param", 5)


@pytest.fixture
def course_catalog_course_count(request):
    return getattr(request, "param", 10)


@pytest.fixture
def course_catalog_data(course_catalog_program_count, course_catalog_course_count):
    """
    Current production data is around 85 courses and 150 course runs. I opted to create 3 of each to allow
    the best course run logic to play out as well as to push the endpoint a little harder in testing.

    There are currently 3 programs in production, so I went with 15, again, to get ready for more data. To allow
    things to be somewhat random, I grab courses for them at random (one required and one elective) which also allows
    for courses to be in more than one program. If we need/want more specific test cases, we can add them, but this
    is a more robust data set than production is presently.

    Returns 3 separate lists to simulate what the tests received prior.

    Args:
        course_catalog_course_count(int): number of courses to generate.
        course_catalog_program_count(int): number of programs to generate.
    """
    programs = []
    courses = []
    course_runs = []
    for n in range(course_catalog_course_count):
        course, course_runs_for_course = _create_course(n)
        courses.append(course)
        course_runs.append(course_runs_for_course)
    for n in range(course_catalog_program_count):
        program = _create_program(courses, n)
        programs.append(program)
    return courses, programs, course_runs


def _create_course(n):
    test_course = CourseFactory.create(title=f"Test Course {n}")
    cr1 = CourseRunFactory.create(course=test_course, past_start=True)
    cr2 = CourseRunFactory.create(course=test_course, in_progress=True)
    cr3 = CourseRunFactory.create(course=test_course, in_future=True)
    return test_course, [cr1, cr2, cr3]


def _create_program(courses, program_index=0):
    program = ProgramFactory.create(title=f"Test Program {program_index:02d}")
    ProgramRequirementFactory.add_root(program)
    root_node = program.requirements_root
    required_courses_node = root_node.add_child(
        node_type=ProgramRequirementNodeType.OPERATOR,
        operator=ProgramRequirement.Operator.ALL_OF,
        title="Required Courses",
    )
    elective_courses_node = root_node.add_child(
        node_type=ProgramRequirementNodeType.OPERATOR,
        operator=ProgramRequirement.Operator.MIN_NUMBER_OF,
        operator_value=2,
        title="Elective Courses",
        elective_flag=True,
    )
    if len(courses) > 3:  # noqa: PLR2004
        # Use deterministic selection based on program index to ensure each 
        # program gets different but predictable courses
        start_idx = (program_index * 2) % len(courses)
        required_course_indices = [(start_idx + i) % len(courses) for i in range(3)]
        elective_course_indices = [(start_idx + 3 + i) % len(courses) for i in range(3)]
        
        for idx in required_course_indices:
            required_courses_node.add_child(
                node_type=ProgramRequirementNodeType.COURSE, course=courses[idx]
            )
        for idx in elective_course_indices:
            elective_courses_node.add_child(
                node_type=ProgramRequirementNodeType.COURSE, course=courses[idx]
            )
    else:
        required_courses_node.add_child(
            node_type=ProgramRequirementNodeType.COURSE, course=courses[0]
        )
    return program
