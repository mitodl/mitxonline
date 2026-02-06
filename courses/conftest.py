"""Shared pytest configuration for courses application"""

import pytest

from b2b.factories import ContractPageFactory
from fixtures.common import user, user_drf_client  # noqa: F401
from courses.factories import (
    CourseFactory,
    CourseRunCertificateFactory,
    CourseRunFactory,
    ProgramCertificateFactory,
    ProgramEnrollmentFactory,
    ProgramFactory,
)
from courses.models import (
    CourseRunEnrollment,
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
def course_catalog_data(
    fake, course_catalog_program_count, course_catalog_course_count
):
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
    for idx in range(course_catalog_course_count):
        course, course_runs_for_course = _create_course(idx)
        courses.append(course)
        course_runs.append(course_runs_for_course)
    for _ in range(course_catalog_program_count):
        program = _create_program(programs, courses, fake)
        programs.append(program)
    return courses, programs, course_runs


def _create_course(idx):
    test_course = CourseFactory.create(title=f"Test Course {idx}")
    cr1 = CourseRunFactory.create(course=test_course, past_start=True)
    cr2 = CourseRunFactory.create(course=test_course, in_progress=True)
    cr3 = CourseRunFactory.create(course=test_course, in_future=True)
    return test_course, [cr1, cr2, cr3]


def _create_program(programs, courses, fake):
    program = ProgramFactory.create()
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

    courses = fake.random_sample(courses, length=min(len(courses), 5))

    # Select 3 courses for required
    for course in courses[:2]:
        required_courses_node.add_child(
            node_type=ProgramRequirementNodeType.COURSE, course=course
        )

    # the rest are electives
    for course in courses[2:]:
        elective_courses_node.add_child(
            node_type=ProgramRequirementNodeType.COURSE, course=course
        )

    if programs:
        # 33% chance this gets a required program
        if fake.boolean(chance_of_getting_true=0.33):
            required_courses_node.add_child(
                node_type=ProgramRequirementNodeType.PROGRAM,
                required_program=fake.random_element(programs),
            )
        # 66% chance this gets an elective program
        if fake.boolean(chance_of_getting_true=0.66):
            elective_courses_node.add_child(
                node_type=ProgramRequirementNodeType.PROGRAM,
                required_program=fake.random_element(programs),
            )

    return program


@pytest.fixture
def b2b_courses(fake, course_catalog_data):
    """Configure some of the courses as b2b"""
    courses, _, _ = course_catalog_data
    contract = ContractPageFactory.create()
    b2b_courses = []

    for course in courses:
        if fake.boolean(chance_of_getting_true=50):
            for run in course.courseruns.all():
                run.b2b_contract = contract
                run.save()
            b2b_courses.append(course)

    return b2b_courses


@pytest.fixture
def user_with_enrollments_and_certificates(fake, user, course_catalog_data):
    """
    Tests the program enrollments API, which should show the user's enrollment
    in programs with the course runs that apply.
    """
    courses, programs, _ = course_catalog_data

    certificate_runs = []

    programs_to_enroll_in = fake.random_sample(programs)
    programs_with_certificate = fake.random_sample(programs_to_enroll_in)

    for program in programs_to_enroll_in:
        ProgramEnrollmentFactory.create(user=user, program=program)
        courses = [
            req.course for req in program.all_requirements.filter(course__isnull=False)
        ]

        if program in programs_with_certificate:
            ProgramCertificateFactory.create(user=user, program=program)

        for course in courses:
            runs = list(course.courseruns.all())
            runs_to_enroll_in = fake.random_sample(runs)
            runs_with_certificate = fake.random_sample(runs_to_enroll_in)

            for run in runs_to_enroll_in:
                CourseRunEnrollment.objects.get_or_create(run=run, user=user)

                if run in runs_with_certificate and run not in certificate_runs:
                    CourseRunCertificateFactory.create(user=user, course_run=run)
                    certificate_runs.append(run)

    return user
