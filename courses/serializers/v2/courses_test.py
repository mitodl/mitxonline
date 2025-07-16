import pytest
from django.contrib.auth.models import AnonymousUser

from cms.serializers import CoursePageSerializer
from courses.factories import (
    CourseFactory,
    CourseRunEnrollmentFactory,
    CourseRunFactory,
    ProgramFactory,
)
from courses.models import CoursesTopic, Department
from courses.serializers.v1.base import BaseProgramSerializer
from courses.serializers.v2.courses import (
    CourseRunSerializer,
    CourseWithCourseRunsSerializer,
)
from main.test_utils import assert_drf_json_equal

pytestmark = [pytest.mark.django_db]


@pytest.mark.parametrize("is_anonymous", [True, False])
@pytest.mark.parametrize("all_runs", [True, False])
@pytest.mark.parametrize(
    "certificate_type", ["MicroMasters Credential", "Certificate of Completion"]
)
def test_serialize_course(
    mocker, mock_context, is_anonymous, all_runs, certificate_type
):
    """Test Course serialization"""
    if is_anonymous:
        mock_context["request"].user = AnonymousUser()
    if all_runs:
        mock_context["all_runs"] = True
    user = mock_context["request"].user
    courseRun1 = CourseRunFactory.create()
    courseRun2 = CourseRunFactory.create(course=courseRun1.course)
    course = courseRun1.course
    topics = [CoursesTopic.objects.create(name=f"topic{num}") for num in range(3)]
    course.page.topics.set([topics[0], topics[1], topics[2]])
    department = "a course departments"
    course.departments.set([Department.objects.create(name=department)])
    program = ProgramFactory.create(program_type="Series")
    if certificate_type == "MicroMasters Credential":
        program.program_type = "MicroMasters®"
    program.add_requirement(course)
    program.save()

    CourseRunEnrollmentFactory.create(
        run=courseRun1, **({} if is_anonymous else {"user": user})
    )

    data = CourseWithCourseRunsSerializer(instance=course, context=mock_context).data

    assert_drf_json_equal(
        data,
        {
            "title": course.title,
            "readable_id": course.readable_id,
            "id": course.id,
            "courseruns": [
                CourseRunSerializer(run).data
                for run in sorted([courseRun1, courseRun2], key=lambda run: run.id)
            ],
            "next_run_id": course.first_unexpired_run.id,
            "max_weekly_hours": course.page.max_weekly_hours,
            "min_weekly_hours": course.page.min_weekly_hours,
            "departments": [{"name": department}],
            "page": CoursePageSerializer(course.page).data,
            "certificate_type": certificate_type,
            "availability": "dated",
            "topics": [{"name": topic.name} for topic in topics],
            "required_prerequisites": True,
            "duration": course.page.length,
            "max_weeks": course.page.max_weeks,
            "min_weeks": course.page.min_weeks,
            "min_price": course.page.min_price,
            "max_price": course.page.max_price,
            "time_commitment": course.page.effort,
            "programs": (
                BaseProgramSerializer(course.programs, many=True).data
                if all_runs
                else None
            ),
        },
    )


@pytest.mark.parametrize("prerequisites_cms_value", ["mock value", None, ""])
def test_serialize_course_required_prerequisites(
    mocker, mock_context, prerequisites_cms_value, settings
):
    """Test Course serialization to ensure that required_prerequisites is set to True if prerequisites is defined in the CMS and no an empty string, otherwise False"""
    course = CourseFactory.create()
    expected_required_prerequisites = False
    if prerequisites_cms_value is not None:
        # When prerequisites_cms_value is None, the course page has been created but prerequisites has never been populated.
        # If the prerequisites have previously been populated but are now empty, the value of prerequisites will be an empty string.
        course.page.prerequisites = prerequisites_cms_value
    if prerequisites_cms_value != "":
        expected_required_prerequisites = True

    data = CourseWithCourseRunsSerializer(instance=course, context=mock_context).data

    assert_drf_json_equal(
        data,
        {
            "title": course.title,
            "readable_id": course.readable_id,
            "id": course.id,
            "courseruns": [],
            "next_run_id": None,
            "max_weekly_hours": course.page.max_weekly_hours,
            "min_weekly_hours": course.page.min_weekly_hours,
            "departments": [],
            "page": CoursePageSerializer(course.page).data,
            "certificate_type": "Certificate of Completion",
            "topics": [],
            "availability": "anytime",
            "required_prerequisites": expected_required_prerequisites,
            "duration": course.page.length,
            "max_weeks": course.page.max_weeks,
            "min_weeks": course.page.min_weeks,
            "min_price": course.page.min_price,
            "max_price": course.page.max_price,
            "time_commitment": course.page.effort,
            "programs": None,
        },
    )
