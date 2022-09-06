"""Factories for creating course data in tests"""
import factory
import faker
import pytz
from factory import SubFactory, Trait, fuzzy
from factory.django import DjangoModelFactory

from courses.constants import PROGRAM_TEXT_ID_PREFIX
from courses.models import (
    Course,
    CourseRun,
    CourseRunEnrollment,
    CourseRunGrade,
    Program,
    ProgramEnrollment,
    ProgramRun,
    BlockedCountry,
)
from users.factories import UserFactory

FAKE = faker.Factory.create()


class ProgramFactory(DjangoModelFactory):
    """Factory for Programs"""

    title = fuzzy.FuzzyText(prefix="Program ")
    readable_id = factory.Sequence(
        lambda number: "{}{}".format(PROGRAM_TEXT_ID_PREFIX, number)
    )
    live = True

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

    program = factory.SubFactory(ProgramFactory)
    position_in_program = None  # will get populated in save()
    title = fuzzy.FuzzyText(prefix="Course ")
    readable_id = factory.Sequence("course-{0}".format)
    live = True

    page = factory.RelatedFactory("cms.factories.CoursePageFactory", "course")

    class Meta:
        model = Course

    class Params:
        no_program = factory.Trait(program=None, position_in_program=None)


class CourseRunFactory(DjangoModelFactory):
    """Factory for CourseRuns"""

    course = factory.SubFactory(CourseFactory, page=None)
    title = factory.LazyAttribute(lambda x: "CourseRun " + FAKE.sentence())
    courseware_id = factory.Sequence(
        lambda number: "course:/v{}/{}".format(number, FAKE.slug())
    )
    run_tag = factory.Sequence("R{0}".format)
    courseware_url_path = factory.Faker("uri")
    start_date = factory.Faker(
        "date_time_this_month", before_now=True, after_now=False, tzinfo=pytz.utc
    )
    end_date = factory.Faker(
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


class CourseRunEnrollmentFactory(DjangoModelFactory):
    """Factory for CourseRunEnrollment"""

    user = SubFactory(UserFactory)
    run = SubFactory(CourseRunFactory)

    class Meta:
        model = CourseRunEnrollment


class ProgramEnrollmentFactory(DjangoModelFactory):
    """Factory for ProgramEnrollment"""

    user = SubFactory(UserFactory)
    program = SubFactory(ProgramFactory)

    class Meta:
        model = ProgramEnrollment
