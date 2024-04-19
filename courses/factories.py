"""Factories for creating course data in tests"""

import string  # noqa: F401
from types import SimpleNamespace

import factory
import faker
import pytest
import pytz
from factory import SubFactory, fuzzy
from factory.django import DjangoModelFactory

from courses.constants import PROGRAM_TEXT_ID_PREFIX
from courses.models import (
    BlockedCountry,
    Course,
    CourseRun,
    CourseRunCertificate,
    CourseRunEnrollment,
    CourseRunGrade,
    Department,
    LearnerProgramRecordShare,
    PartnerSchool,
    Program,
    ProgramCertificate,
    ProgramEnrollment,
    ProgramRequirement,
    ProgramRequirementNodeType,
    ProgramRun,
)
from users.factories import UserFactory

FAKE = faker.Factory.create()


class DepartmentFactory(DjangoModelFactory):
    name = factory.Sequence(lambda x: f"Testing - {x} Department")

    class Meta:
        model = Department


class ProgramFactory(DjangoModelFactory):
    """Factory for Programs"""

    title = fuzzy.FuzzyText(prefix="Program ")
    readable_id = factory.Sequence(lambda number: f"{PROGRAM_TEXT_ID_PREFIX}{number}")
    live = True

    page = factory.RelatedFactory("cms.factories.ProgramPageFactory", "program")

    @factory.post_generation
    def departments(self, create, extracted, **kwargs):  # noqa: ARG002
        if not create or not extracted:
            return
        self.departments.add(*extracted)

    class Meta:
        model = Program


class ProgramRunFactory(DjangoModelFactory):
    """Factory for ProgramRuns"""

    program = factory.SubFactory(ProgramFactory)
    run_tag = factory.Sequence("R{0}".format)

    class Meta:
        model = ProgramRun


class CourseFactory(DjangoModelFactory):
    """Factory for Courses"""

    title = fuzzy.FuzzyText(prefix="Course ")
    readable_id = factory.Sequence("course-{0}".format)
    live = True
    departments = factory.SubFactory(DepartmentFactory)

    page = factory.RelatedFactory("cms.factories.CoursePageFactory", "course")

    @factory.post_generation
    def departments(self, create, extracted, **kwargs):  # noqa: ARG002
        if not create or not extracted:
            return
        self.departments.add(*extracted)

    class Meta:
        model = Course


class CourseRunFactory(DjangoModelFactory):
    """Factory for CourseRuns"""

    course = factory.SubFactory(CourseFactory)
    title = factory.LazyAttribute(lambda x: "CourseRun " + FAKE.sentence())  # noqa: ARG005
    courseware_id = factory.Sequence(lambda number: f"course:/v{number}/{FAKE.slug()}")
    run_tag = factory.Sequence("R{0}".format)
    courseware_url_path = factory.Faker("uri")
    start_date = factory.Faker(
        "date_time_this_month", before_now=True, after_now=False, tzinfo=pytz.utc
    )
    end_date = factory.Faker(
        "date_time_this_year", before_now=False, after_now=True, tzinfo=pytz.utc
    )
    certificate_available_date = factory.Faker(
        "date_time_this_year", before_now=False, after_now=True, tzinfo=pytz.utc
    )

    enrollment_start = factory.Faker(
        "date_time_this_month", before_now=True, after_now=False, tzinfo=pytz.utc
    )
    enrollment_end = factory.Faker(
        "date_time_this_month", before_now=False, after_now=True, tzinfo=pytz.utc
    )
    expiration_date = factory.Faker(
        "date_time_between", start_date="+1y", end_date="+2y", tzinfo=pytz.utc
    )
    upgrade_deadline = factory.Faker(
        "date_time_between", start_date="+1y", end_date="+2y", tzinfo=pytz.utc
    )

    live = True

    class Meta:
        model = CourseRun

    class Params:
        past_start = factory.Trait(
            start_date=factory.Faker("past_datetime", tzinfo=pytz.utc)
        )
        past_enrollment_end = factory.Trait(
            enrollment_end=factory.Faker("past_datetime", tzinfo=pytz.utc)
        )
        in_progress = factory.Trait(
            start_date=factory.Faker("past_datetime", tzinfo=pytz.utc),
            end_date=factory.Faker("future_datetime", tzinfo=pytz.utc),
        )
        in_future = factory.Trait(
            start_date=factory.Faker("future_datetime", tzinfo=pytz.utc), end_date=None
        )


NODE_TYPES = [x[0] for x in ProgramRequirementNodeType.choices]
OPERATORS = [x[0] for x in ProgramRequirement.Operator.choices]
OPERATOR_VALUES = [str(x) for x in range(1, 11)]
TITLES = ["Required Courses", "Elective Courses"]


class ProgramRequirementFactory(DjangoModelFactory):
    """Factory for Program Requirement"""

    node_type = fuzzy.FuzzyChoice(NODE_TYPES)
    operator = fuzzy.FuzzyChoice(OPERATORS)
    operator_value = fuzzy.FuzzyChoice(OPERATOR_VALUES)

    program = factory.SubFactory(ProgramFactory)
    course = factory.SubFactory(CourseFactory)
    title = fuzzy.FuzzyChoice(TITLES)

    class Meta:
        model = ProgramRequirement

    @classmethod
    def add_root(cls, program):
        if not ProgramRequirement.get_root_nodes().filter(program=program).exists():
            return ProgramRequirement.add_root(
                program=program, node_type=ProgramRequirementNodeType.PROGRAM_ROOT.value
            )
        return program.get_requirements_root()


class BlockedCountryFactory(DjangoModelFactory):
    """Factory for BlockedCountry"""

    course = factory.SubFactory(CourseFactory)
    country = factory.Faker("country_code", representation="alpha-2")

    class Meta:
        model = BlockedCountry


class CourseRunGradeFactory(DjangoModelFactory):
    """Factory for CourseRunGrade"""

    course_run = factory.SubFactory(CourseRunFactory)
    user = factory.SubFactory(UserFactory)
    grade = factory.fuzzy.FuzzyDecimal(low=0.0, high=1.0)
    letter_grade = factory.fuzzy.FuzzyText(length=1)
    passed = factory.fuzzy.FuzzyChoice([True, False])
    set_by_admin = factory.fuzzy.FuzzyChoice([True, False])

    class Meta:
        model = CourseRunGrade


class ProgramCertificateFactory(DjangoModelFactory):
    """Factory for ProgramCertificate"""

    program = factory.SubFactory(ProgramFactory)
    user = factory.SubFactory(UserFactory)
    certificate_page_revision = None

    class Meta:
        model = ProgramCertificate


class CourseRunEnrollmentFactory(DjangoModelFactory):
    """Factory for CourseRunEnrollment"""

    user = SubFactory(UserFactory)
    run = SubFactory(CourseRunFactory)

    class Meta:
        model = CourseRunEnrollment


class CourseRunCertificateFactory(DjangoModelFactory):
    """Factory for CourseRunCertificate"""

    course_run = factory.SubFactory(CourseRunFactory)
    user = factory.SubFactory(UserFactory)
    certificate_page_revision = None

    class Meta:
        model = CourseRunCertificate


class ProgramEnrollmentFactory(DjangoModelFactory):
    """Factory for ProgramEnrollment"""

    user = SubFactory(UserFactory)
    program = SubFactory(ProgramFactory)

    class Meta:
        model = ProgramEnrollment


class PartnerSchoolFactory(DjangoModelFactory):
    name = fuzzy.FuzzyText(prefix="Program ")
    email = fuzzy.FuzzyText(suffix="@example.com")

    class Meta:
        model = PartnerSchool


class LearnerProgramRecordShareFactory(DjangoModelFactory):
    user = SubFactory(UserFactory)
    program = SubFactory(ProgramFactory)
    partner_school = SubFactory(PartnerSchoolFactory)
    is_active = fuzzy.FuzzyInteger(0, 1, 1)

    class Meta:
        model = LearnerProgramRecordShare


@pytest.fixture
def program_with_empty_requirements():
    program = ProgramFactory.create()
    ProgramRequirementFactory.add_root(program)
    root_node = program.requirements_root

    root_node.add_child(
        node_type=ProgramRequirementNodeType.OPERATOR,
        operator=ProgramRequirement.Operator.ALL_OF,
        title="Required Courses",
    )
    root_node.add_child(
        node_type=ProgramRequirementNodeType.OPERATOR,
        operator=ProgramRequirement.Operator.MIN_NUMBER_OF,
        operator_value=1,
        title="Elective Courses",
        elective_flag=True,
    )
    return program


@pytest.fixture
def program_with_requirements():
    program = ProgramFactory.create()
    required_courses = CourseFactory.create_batch(3)
    elective_courses = CourseFactory.create_batch(3)
    mut_exclusive_courses = CourseFactory.create_batch(3)

    root_node = program.requirements_root

    required_courses_node = root_node.add_child(
        node_type=ProgramRequirementNodeType.OPERATOR,
        operator=ProgramRequirement.Operator.ALL_OF,
        title="Required Courses",
    )
    for course in required_courses:
        required_courses_node.add_child(
            node_type=ProgramRequirementNodeType.COURSE, course=course
        )

    # at least two must be taken
    elective_courses_node = root_node.add_child(
        node_type=ProgramRequirementNodeType.OPERATOR,
        operator=ProgramRequirement.Operator.MIN_NUMBER_OF,
        operator_value=2,
        title="Elective Courses",
        elective_flag=True,
    )
    for course in elective_courses:
        elective_courses_node.add_child(
            node_type=ProgramRequirementNodeType.COURSE, course=course
        )

    # 3rd elective option is at least one of these courses
    mut_exclusive_courses_node = elective_courses_node.add_child(
        node_type=ProgramRequirementNodeType.OPERATOR,
        operator=ProgramRequirement.Operator.MIN_NUMBER_OF,
        operator_value=1,
    )
    for course in mut_exclusive_courses:
        mut_exclusive_courses_node.add_child(
            node_type=ProgramRequirementNodeType.COURSE, course=course
        )

    return SimpleNamespace(
        program=program,
        root_node=root_node,
        required_courses=required_courses,
        required_courses_node=required_courses_node,
        elective_courses=elective_courses,
        elective_courses_node=elective_courses_node,
        mut_exclusive_courses=mut_exclusive_courses,
        mut_exclusive_courses_node=mut_exclusive_courses_node,
    )
