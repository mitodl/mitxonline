"""Shared pytest configuration for courses application"""

from collections import defaultdict
from math import ceil
from typing import NamedTuple

import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from faker import Faker
from opaque_keys.edx.keys import CourseKey

from b2b.factories import ContractPageFactory, OrganizationPageFactory
from b2b.models import ContractPage, OrganizationPage
from courses.constants import COURSE_VARIANT_INDUSTRY, COURSE_VARIANT_LENGTH
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
from variants.models import SupportedVariant

User = get_user_model()
langopts = [
    "de_DE",
    "fr",
    "ar",
    "zh_CN",
]
fake = Faker()
COURSERUN_EXCLUDE_KEYS = [
    "_state",
    "id",
]


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
    crvs = []
    if idx % 2:
        # Make some variant runs - by default, half of the courses should get one.
        # These are for normal, customer-facing courses, so the only variants we'll
        # configure are translations.
        language = fake.random_element(langopts)
        SupportedVariant.objects.create(variant_object=test_course, language=language)
        crv1 = CourseRunFactory.create(
            course=test_course,
            past_start=True,
            courseware_id=f"{cr1.courseware_id}_{language}",
            language=language,
            is_primary_language=False,
            run_tag=cr1.run_tag,
        )
        crv2 = CourseRunFactory.create(
            course=test_course,
            past_start=True,
            courseware_id=f"{cr2.courseware_id}_{language}",
            language=language,
            is_primary_language=False,
            run_tag=cr2.run_tag,
        )
        crv3 = CourseRunFactory.create(
            course=test_course,
            past_start=True,
            courseware_id=f"{cr3.courseware_id}_{language}",
            language=language,
            is_primary_language=False,
            run_tag=cr3.run_tag,
        )
        crvs = [
            crv1,
            crv2,
            crv3,
        ]
    return test_course, [
        cr1,
        cr2,
        cr3,
        *crvs,
    ]


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


def _create_source_variant_runs(course, *, b2b_only=True):
    """
    Create source (and source variant) runs for the course.

    The default is "english,," so you always get one of those.

    If the course has variants configured already, it will create source runs
    accordingly. If it doesn't, you will get 3 with randomly-selected language,
    industry and length options. They will be B2B only if the `b2b_only` is set.
    """

    if course.possible_variant_sets.filter(
        default_variant=False, b2b_only=b2b_only
    ).exists():
        variants = [
            (opt.langauge, opt.industry, opt.length)
            for opt in course.possible_variant_sets.filter(
                default_variant=False, b2b_only=b2b_only
            ).all()
        ]
    else:
        # as long as the language is unique, the other two can repeat
        random_langs = fake.random_sample(langopts, length=3)
        variants = [
            (
                random_langs[0],
                fake.random_element(COURSE_VARIANT_INDUSTRY[1:])[0],
                fake.random_element(COURSE_VARIANT_LENGTH[1:])[0],
            ),
            (
                random_langs[1],
                fake.random_element(COURSE_VARIANT_INDUSTRY[1:])[0],
                fake.random_element(COURSE_VARIANT_LENGTH[1:])[0],
            ),
            (
                random_langs[2],
                fake.random_element(COURSE_VARIANT_INDUSTRY[1:])[0],
                fake.random_element(COURSE_VARIANT_LENGTH[1:])[0],
            ),
        ]

        for variant in variants:
            SupportedVariant.objects.create(
                variant_object=course,
                language=variant[0],
                variant_industry=variant[1],
                variant_length=variant[2],
                b2b_only=b2b_only,
            )

    variant_sources = []

    primary_source_run = CourseRunFactory.create(
        course=course,
        is_source_run=True,
        language="en",
        is_primary_language=True,
    )
    variant_sources.append(primary_source_run)

    exclude_keys = [
        *COURSERUN_EXCLUDE_KEYS,
        "courseware_id",
        "language",
        "is_primary_language",
        "variant_industry",
        "variant_length",
    ]

    psr_fields = {
        k: getattr(primary_source_run, k)
        for k in primary_source_run.__dict__.keys() - exclude_keys
    }

    for variant in variants:
        (lang, vind, vlen) = variant

        source_run = CourseRunFactory.create(
            **psr_fields,
            courseware_id=f"{primary_source_run.courseware_id}_{lang}_{vind}_{vlen}",
            language=lang,
            is_primary_language=False,
            variant_industry=vind,
            variant_length=vlen,
        )
        variant_sources.append(source_run)

    return variant_sources


def _create_b2b_run_from_source(contract, source_run, run_tag_prefix):
    """Create a B2B run for the specified contract and source run"""

    exclude_keys = [
        *COURSERUN_EXCLUDE_KEYS,
        "is_source_run",
        "courseware_id",
        "run_tag",
        "b2b_contract_id",
    ]

    sr_fields = {
        k: getattr(source_run, k) for k in source_run.__dict__.keys() - exclude_keys
    }

    run_tag = f"{run_tag_prefix}_{source_run.language}_{source_run.variant_industry}_{source_run.variant_length}"

    run_key = CourseKey.from_string(source_run.courseware_id)
    run_key = run_key.replace(org=contract.organization.org_key, run=run_tag)

    return CourseRunFactory.create(
        **sr_fields,
        is_source_run=False,
        courseware_id=str(run_key),
        run_tag=run_tag_prefix,
        b2b_contract=contract,
    )


def _process_variants_and_runs(contract, course):
    """Make sure the contract supports the course variants, add contract runs"""

    run_tag_prefix_semester = fake.random_digit_not_null()
    run_tag_prefix_year = fake.future_date(end_date="+3y").year
    contract_content_type = ContentType.objects.get_for_model(contract)

    [
        SupportedVariant.objects.update_or_create(
            object_id=contract.id,
            content_type=contract_content_type,
            language=cv.language,
            variant_industry=cv.variant_industry,
            variant_length=cv.variant_length,
            default_variant=cv.default_variant,
        )
        for cv in course.possible_variant_sets.all()
    ]

    return [
        _create_b2b_run_from_source(
            contract, sr, f"{run_tag_prefix_semester}T{run_tag_prefix_year}"
        )
        for sr in course.courseruns.filter(is_source_run=True).all()
    ]


@pytest.fixture
def b2b_courses(fake, course_catalog_data):
    """Configure some of the courses as b2b"""
    courses, _, course_runs = course_catalog_data
    organizations = OrganizationPageFactory.create_batch(3)
    contracts = []
    contracts_by_org_id = {}
    course_runs_by_contract_id = defaultdict(list)
    course_runs_by_org_id = defaultdict(list)

    for org in organizations:
        org_contracts = ContractPageFactory.create_batch(3, organization=org)
        contracts_by_org_id[org.id] = org_contracts
        contracts.extend(org_contracts)

    [_create_source_variant_runs(course) for course in courses]

    for contract in contracts:
        contract_runs = []
        for course in fake.random_sample(courses, length=ceil(len(courses) * 0.5)):
            contract_runs.extend(_process_variants_and_runs(contract, course))

        course_runs.extend(contract_runs)
        course_runs_by_contract_id[contract.id] = contract_runs
        course_runs_by_org_id[contract.organization.id].extend(contract_runs)

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
