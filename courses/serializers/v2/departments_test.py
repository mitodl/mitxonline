import pytest

from courses.factories import (
    CourseFactory,
    CourseRunFactory,
    DepartmentFactory,
    ProgramFactory,
)
from courses.serializers.v2.departments import (
    DepartmentSerializer,
    DepartmentWithCoursesAndProgramsSerializer,
)
from main.test_utils import assert_drf_json_equal


def test_serialize_department(mock_context):
    department = DepartmentFactory.create()
    data = DepartmentSerializer(instance=department, context=mock_context).data

    assert_drf_json_equal(
        data, {"id": department.id, "name": department.name, "slug": department.slug}
    )


# Should return 0 when there are no courses or programs at all, or when there are, but none are relevant
def test_serialize_department_with_courses_and_programs__no_related(mock_context):
    department = DepartmentFactory.create()
    data = DepartmentWithCoursesAndProgramsSerializer(
        instance=department, context=mock_context
    ).data
    assert_drf_json_equal(
        data,
        {
            "id": department.id,
            "name": department.name,
            "course_ids": [],
            "program_ids": [],
            "slug": department.slug,
        },
    )

    course = CourseFactory.create()
    CourseRunFactory.create(course=course, in_future=True)
    ProgramFactory.create()
    data = DepartmentWithCoursesAndProgramsSerializer(
        instance=department, context=mock_context
    ).data
    assert_drf_json_equal(
        data,
        {
            "id": department.id,
            "name": department.name,
            "course_ids": [],
            "program_ids": [],
            "slug": department.slug,
        },
    )


@pytest.mark.parametrize(
    "valid_courses,valid_programs,invalid_courses,invalid_programs",  # noqa: PT006
    [(0, 0, 0, 0), (1, 1, 0, 0), (0, 0, 1, 1), (2, 2, 0, 0), (2, 2, 1, 1)],
)
def test_serialize_department_with_courses_and_programs__with_multiples(
    mock_context,
    valid_courses,
    valid_programs,
    invalid_courses,
    invalid_programs,
):
    department = DepartmentFactory.create()
    valid_course_id_list = []
    valid_program_id_list = []

    vc = valid_courses
    while vc > 0:
        course = CourseFactory.create(departments=[department])
        # Each course has 2 course runs that are possible matches to make sure it is not returned twice.
        CourseRunFactory.create(course=course, in_future=True)
        CourseRunFactory.create(course=course, in_progress=True)
        valid_course_id_list.append(course.id)
        vc -= 1
    vp = valid_programs
    while vp > 0:
        valid_program_id_list.append(ProgramFactory.create(departments=[department]).id)
        vp -= 1
    while invalid_courses > 0:
        invalid_courses -= 1
    while invalid_programs > 0:
        invalid_programs -= 1
    data = DepartmentWithCoursesAndProgramsSerializer(
        instance=department, context=mock_context
    ).data
    assert_drf_json_equal(
        data,
        {
            "id": department.id,
            "name": department.name,
            "course_ids": valid_course_id_list,
            "program_ids": valid_program_id_list,
            "slug": department.slug,
        },
    )
