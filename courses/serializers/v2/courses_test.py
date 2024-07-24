import pytest
from django.contrib.auth.models import AnonymousUser

from cms.serializers import CoursePageSerializer
from courses.factories import (
    CourseRunEnrollmentFactory,
    CourseRunFactory,
    ProgramFactory,
)
from courses.models import Department
from courses.serializers.v1.courses import (
    CourseRunSerializer,
    CourseWithCourseRunsSerializer,
)
from courses.serializers.v1.programs import ProgramSerializer
from main.test_utils import assert_drf_json_equal

pytestmark = [pytest.mark.django_db]


@pytest.mark.parametrize("is_anonymous", [True, False])
@pytest.mark.parametrize("all_runs", [True, False])
@pytest.mark.parametrize("certificate_type", ["MicroMasters Credential", "Certificate of Completion"])
def test_serialize_course(mocker, mock_context, is_anonymous, all_runs, certificate_type, settings):
    """Test Course serialization"""
    if is_anonymous:
        mock_context["request"].user = AnonymousUser()
    if all_runs:
        mock_context["all_runs"] = True
    user = mock_context["request"].user
    courseRun1 = CourseRunFactory.create()
    courseRun2 = CourseRunFactory.create(course=courseRun1.course)
    course = courseRun1.course
    department = "a course departments"
    course.departments.set([Department.objects.create(name=department)])
    if certificate_type == "MicroMasters Credential":
        program = ProgramFactory.create(program_type="MicroMasters®")
        program.add_requirement(course)

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
            "programs": ProgramSerializer(course.programs, many=True).data
            if all_runs
            else None,
        },
    )
