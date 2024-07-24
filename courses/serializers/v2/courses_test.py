import pytest
from django.contrib.auth.models import AnonymousUser

from cms.serializers import CoursePageSerializer
from courses.factories import (
    CourseRunEnrollmentFactory,
    CourseRunFactory,
    ProgramFactory,
)
from courses.models import Department, CoursesTopic
from courses.serializers.v2.courses import (
    CourseRunSerializer,
    CourseWithCourseRunsSerializer,
)
from courses.serializers.v2.programs import ProgramSerializer
from main.test_utils import assert_drf_json_equal

pytestmark = [pytest.mark.django_db]


@pytest.mark.parametrize("is_anonymous", [True, False])
@pytest.mark.parametrize("all_runs", [True, False])
@pytest.mark.parametrize("certificate_type", ["MicroMasters Credential", "Certificate of Completion"])
def test_serialize_course(mocker, mock_context, is_anonymous, all_runs, certificate_type):
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
                CourseRunSerializer(courseRun1).data,
                CourseRunSerializer(courseRun2).data,
            ],
            "next_run_id": course.first_unexpired_run.id,
            "departments": [{"name": department}],
            "page": CoursePageSerializer(course.page).data,
            "certificate_type": certificate_type,
            "topics": [{"name": topic.name} for topic in topics],
            "programs": ProgramSerializer(course.programs, many=True).data
            if all_runs
            else None,
        },
    )
