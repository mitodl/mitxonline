"""Shared pytest configuration for courses application"""

from collections import defaultdict
from math import ceil
from typing import NamedTuple

import pytest
from django.contrib.auth import get_user_model

from b2b.factories import ContractPageFactory, OrganizationPageFactory
from b2b.models import ContractPage, OrganizationPage
from courses.factories import (
    CourseFactory,
    CourseRunCertificateFactory,
    CourseRunEnrollmentFactory,
    CourseRunFactory,
    ProgramCertificateFactory,
    ProgramEnrollmentFactory,
    ProgramFactory,
)
from courses.models import (
    Course,
    CourseRun,
    CourseRunCertificate,
    CourseRunEnrollment,
    Program,
    ProgramCertificate,
    ProgramEnrollment,
    ProgramRequirement,
    ProgramRequirementNodeType,
)

User = get_user_model()


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


class CourseCatalogData(NamedTuple):
    courses: list[Course]
    programs: list[Program]
    course_runs: list[CourseRun]


@pytest.fixture
def course_catalog_data(
    fake, course_catalog_program_count, course_catalog_course_count
) -> CourseCatalogData:
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
        course_runs.extend(course_runs_for_course)
    for _ in range(course_catalog_program_count):
        program = _create_program(programs, courses, fake)
        programs.append(program)
    return CourseCatalogData(courses, programs, course_runs)


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


class B2BCourses(NamedTuple):
    organizations: list[OrganizationPage]
    contracts_by_org_id: dict[int, ContractPage]
    course_runs: list[CourseRun]
    course_runs_by_contract_id: dict[int, list[CourseRun]]
    course_runs_by_org_id: dict[int, list[CourseRun]]


@pytest.fixture
def b2b_courses(fake, course_catalog_data):
    """Configure some of the courses as b2b"""
    _, _, runs = course_catalog_data
    organizations = OrganizationPageFactory.create_batch(3)
    contracts = []
    contracts_by_org_id = {}
    course_runs = []
    course_runs_by_contract_id = defaultdict(list)
    course_runs_by_org_id = defaultdict(list)

    for org in organizations:
        org_contracts = ContractPageFactory.create_batch(3)
        contracts_by_org_id[org.id] = org_contracts
        contracts.extend(org_contracts)

    for run in fake.random_sample(runs, length=ceil(len(runs) * 0.5)):
        contract = fake.random_element(elements=contracts)

        run.b2b_contract = contract
        run.save()

        course_runs.append(run)
        course_runs_by_contract_id[contract.id].append(run)
        course_runs_by_org_id[contract.organization_id].append(run)

    return B2BCourses(
        organizations=organizations,
        contracts_by_org_id=contracts_by_org_id,
        course_runs=course_runs,
        course_runs_by_contract_id=course_runs_by_contract_id,
        course_runs_by_org_id=course_runs_by_org_id,
    )


@pytest.fixture
def user_run_enrollment_count(request, course_catalog_data: CourseCatalogData):
    course_count = len(course_catalog_data.courses)
    count = getattr(request, "param", ceil(course_count * 0.7))
    if count > course_count:
        return pytest.fail("Cannot have more certificates than courses")
    return count


@pytest.fixture
def user_run_certificate_count(request, user_run_enrollment_count):
    count = getattr(request, "param", ceil(user_run_enrollment_count * 0.7))
    if count > user_run_enrollment_count:
        return pytest.fail("Cannot have more run certificates than run enrollments")
    return count


@pytest.fixture
def user_program_enrollment_count(request, course_catalog_data):
    program_count = len(course_catalog_data.programs)
    count = getattr(request, "param", ceil(program_count * 0.7))
    if count > program_count:
        return pytest.fail("Cannot have more certificates than programs")
    return count


@pytest.fixture
def user_program_certificate_count(request, user_program_enrollment_count):
    count = getattr(request, "param", ceil(user_program_enrollment_count * 0.7))
    if count > user_program_enrollment_count:
        return pytest.fail(
            "Cannot have more program certificates than program enrollments"
        )
    return count


class UserEnrollmentConfig(NamedTuple):
    run_enrollment_count: int
    run_certificate_count: int
    program_enrollment_count: int
    program_certificate_count: int


@pytest.fixture
def user_enrollment_config(
    request,
    user_run_enrollment_count,
    user_run_certificate_count,
    user_program_enrollment_count,
    user_program_certificate_count,
) -> UserEnrollmentConfig:
    return getattr(
        request,
        "param",
        UserEnrollmentConfig(
            user_run_enrollment_count,
            user_run_certificate_count,
            user_program_enrollment_count,
            user_program_certificate_count,
        ),
    )


class UserWithEnrollmentsAndCerts(NamedTuple):
    user: User
    run_enrollments: list[CourseRunEnrollment]
    run_certificates: list[CourseRunCertificate]
    program_enrollments: list[ProgramEnrollment]
    program_certificates: list[ProgramCertificate]


@pytest.fixture
def user_with_enrollments_and_certificates(
    fake,
    user,
    course_catalog_data: CourseCatalogData,
    user_enrollment_config: UserEnrollmentConfig,
):
    """
    Fixture for a user with enrollments and certificates
    """
    _, programs, course_runs = course_catalog_data

    programs_to_enroll_in = fake.random_sample(
        programs, length=user_enrollment_config.program_enrollment_count
    )
    programs_with_certificate = fake.random_sample(
        programs_to_enroll_in, length=user_enrollment_config.program_enrollment_count
    )

    runs_to_enroll_in = fake.random_sample(
        course_runs, length=user_enrollment_config.run_enrollment_count
    )
    runs_with_certificate = fake.random_sample(
        runs_to_enroll_in, length=user_enrollment_config.run_certificate_count
    )

    program_enrollments = [
        ProgramEnrollmentFactory.create(user=user, program=program)
        for program in programs_to_enroll_in
    ]
    program_certificates = [
        ProgramCertificateFactory.create(user=user, program=program)
        for program in programs_with_certificate
    ]
    run_enrollments = [
        CourseRunEnrollmentFactory.create(run=run, user=user)
        for run in runs_to_enroll_in
    ]
    run_certificates = [
        CourseRunCertificateFactory.create(user=user, course_run=run)
        for run in runs_with_certificate
    ]

    return UserWithEnrollmentsAndCerts(
        user=user,
        run_enrollments=run_enrollments,
        run_certificates=run_certificates,
        program_enrollments=program_enrollments,
        program_certificates=program_certificates,
    )
