from datetime import timedelta

import pytest
from django.utils.timezone import now

from cms.serializers import ProgramPageSerializer
from courses.factories import CourseRunFactory, program_with_empty_requirements
from courses.models import Department
from courses.serializers.v2.programs import ProgramSerializer, ProgramRequirementTreeSerializer
from main.test_utils import assert_drf_json_equal

pytestmark = [pytest.mark.django_db]


@pytest.mark.parametrize(
    "remove_tree",
    [True, False],
)
def test_serialize_program(mock_context, remove_tree, program_with_empty_requirements):
    """Test Program serialization"""
    run1 = CourseRunFactory.create(
        course__page=None,
        start_date=now() + timedelta(hours=1),
    )
    course1 = run1.course
    run2 = CourseRunFactory.create(
        course__page=None,
        start_date=now() + timedelta(hours=2),
    )
    course2 = run2.course
    departments = [
        Department.objects.create(name=f"department{num}") for num in range(3)
    ]
    course1.departments.set([departments[0], departments[1]])
    course2.departments.set([departments[1], departments[2]])

    formatted_reqs = {"required": [], "electives": []}

    if not remove_tree:
        program_with_empty_requirements.add_requirement(course1)
        program_with_empty_requirements.add_requirement(course2)
        formatted_reqs["required"] = [
            course.id for course in program_with_empty_requirements.required_courses
        ]
        formatted_reqs["electives"] = [
            course.id for course in program_with_empty_requirements.elective_courses
        ]

    data = ProgramSerializer(
        instance=program_with_empty_requirements, context=mock_context
    ).data

    assert_drf_json_equal(
        data,
        {
            "title": program_with_empty_requirements.title,
            "readable_id": program_with_empty_requirements.readable_id,
            "id": program_with_empty_requirements.id,
            "courses": [course.id for course in [course1, course2]]
            if not remove_tree
            else [],
            "requirements": formatted_reqs,
            "req_tree": ProgramRequirementTreeSerializer(
                program_with_empty_requirements.requirements_root
            ).data,
            "page": ProgramPageSerializer(program_with_empty_requirements.page).data,
            "program_type": "Series",
            "departments": [],
            "live": True,
        },
    )
