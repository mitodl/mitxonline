from datetime import timedelta
from unittest.mock import ANY

import pytest
from django.utils.timezone import now

from cms.factories import CoursePageFactory
from cms.serializers import ProgramPageSerializer
from courses.factories import (  # noqa: F401
    CourseFactory,
    CourseRunFactory,
    ProgramCollectionFactory,
    ProgramFactory,
    program_with_empty_requirements,
)
from courses.models import CoursesTopic, Department, ProgramCollectionItem
from courses.serializers.v1.departments import DepartmentSerializer
from courses.serializers.v2.programs import (
    ProgramRequirementTreeSerializer,
    ProgramSerializer,
)
from main.test_utils import assert_drf_json_equal

pytestmark = [pytest.mark.django_db]


@pytest.mark.parametrize("remove_tree", [True, False])
@pytest.mark.parametrize(
    "certificate_type", ["MicroMasters Credential", "Certificate of Completion"]
)
@pytest.mark.parametrize("prerequisites", ["program prerequisites", None, ""])
def test_serialize_program(
    mock_context,
    remove_tree,
    certificate_type,
    prerequisites,
    program_with_empty_requirements,  # noqa: F811
):
    """Test Program serialization"""
    if certificate_type == "MicroMasters Credential":
        program_with_empty_requirements.program_type = "MicroMasters®"
        program_with_empty_requirements.save()

    required_prerequisites = False
    if prerequisites is not None:
        program_with_empty_requirements.page.prerequisites = prerequisites
    if prerequisites != "":
        required_prerequisites = True

    run1 = CourseRunFactory.create(
        course__page=None,
        start_date=now() + timedelta(hours=1),
    )
    course1 = run1.course
    CoursePageFactory.create(course=run1.course)
    run2 = CourseRunFactory.create(
        course__page=None,
        start_date=now() + timedelta(hours=2),
    )
    course2 = run2.course
    CoursePageFactory.create(course=run2.course)
    program_collection = ProgramCollectionFactory.create(
        title="Test Collection",
    )
    ProgramCollectionItem.objects.create(
        collection=program_collection,
        program=program_with_empty_requirements,
        sort_order=0,
    )
    required_program = ProgramFactory.create(
        page=None,
        title="Required Program",
    )

    formatted_reqs = {
        "courses": {"required": [], "electives": []},
        "programs": {"required": [], "electives": []},
    }

    topics = []
    if not remove_tree:
        program_with_empty_requirements.add_requirement(course1)
        program_with_empty_requirements.add_requirement(course2)
        program_with_empty_requirements.add_requirement(required_program)
        formatted_reqs["courses"]["required"] = [
            {"id": course.id, "readable_id": course.readable_id}
            for course in program_with_empty_requirements.required_courses
        ]
        formatted_reqs["courses"]["electives"] = [
            {"id": course.id, "readable_id": course.readable_id}
            for course in program_with_empty_requirements.elective_courses
        ]
        formatted_reqs["programs"]["required"] = [
            {"id": program.id, "readable_id": program.readable_id}
            for program in program_with_empty_requirements.required_programs
        ]
        formatted_reqs["programs"]["electives"] = [
            {"id": program.id, "readable_id": program.readable_id}
            for program in program_with_empty_requirements.elective_programs
        ]
        topics = [CoursesTopic.objects.create(name=f"topic{num}") for num in range(3)]
        course1.page.topics.set([topics[0], topics[1]])
        course2.page.topics.set([topics[1], topics[2]])
        course1.page.save()
        course2.page.save()
    program_department = Department.objects.create(name="Math")
    program_with_empty_requirements.departments.add(program_department)

    first_unexpired_run = program_with_empty_requirements.first_unexpired_run

    if not remove_tree:
        expected_start_date = first_unexpired_run.start_date
    else:
        expected_start_date = program_with_empty_requirements.start_date

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
            "collections": [program_collection.id],
            "requirements": formatted_reqs,
            "req_tree": ProgramRequirementTreeSerializer(
                program_with_empty_requirements.requirements_root
            ).data,
            "page": ProgramPageSerializer(program_with_empty_requirements.page).data,
            "program_type": program_with_empty_requirements.program_type,
            "certificate_type": certificate_type,
            "departments": [DepartmentSerializer(program_department).data],
            "live": True,
            "topics": [{"name": topic.name} for topic in topics],
            "availability": "anytime",
            "start_date": expected_start_date,
            "end_date": program_with_empty_requirements.end_date,
            "enrollment_start": program_with_empty_requirements.enrollment_start,
            "enrollment_end": program_with_empty_requirements.enrollment_end,
            "required_prerequisites": required_prerequisites,
            "duration": program_with_empty_requirements.page.length,
            "max_weeks": program_with_empty_requirements.page.max_weeks,
            "min_weeks": program_with_empty_requirements.page.min_weeks,
            "time_commitment": program_with_empty_requirements.page.effort,
            "max_weekly_hours": program_with_empty_requirements.page.max_weekly_hours,
            "min_weekly_hours": program_with_empty_requirements.page.min_weekly_hours,
            "min_price": program_with_empty_requirements.page.min_price,
            "max_price": program_with_empty_requirements.page.max_price,
            "products": [],
        },
    )


def test_serialize_program_with_products(
    mock_context,
    program_with_empty_requirements,  # noqa: F811
):
    """Test Program serialization includes product data"""
    from ecommerce.factories import ProductFactory  # noqa: PLC0415

    product = ProductFactory.create(purchasable_object=program_with_empty_requirements)

    data = ProgramSerializer(
        instance=program_with_empty_requirements, context=mock_context
    ).data

    assert len(data["products"]) == 1
    assert data["products"][0]["id"] == product.id
    assert data["products"][0]["price"] == str(product.price)
    assert data["products"][0]["is_active"] == product.is_active
    assert data["products"][0]["description"] == product.description


def test_program_requirement_tree_serializer_save():
    """Verify that the ProgramRequirementTreeSerializer validates data"""
    program = ProgramFactory.create()
    course1, course2, course3 = CourseFactory.create_batch(3)
    root = program.requirements_root

    serializer = ProgramRequirementTreeSerializer(
        instance=root,
        data=[
            {
                "data": {
                    "node_type": "operator",
                    "title": "Required Courses",
                    "operator": "all_of",
                },
                "children": [
                    {"id": None, "data": {"node_type": "course", "course": course1.id}}
                ],
            },
            {
                "data": {
                    "node_type": "operator",
                    "title": "Elective Courses",
                    "operator": "min_number_of",
                    "operator_value": "1",
                },
                "children": [
                    {"id": None, "data": {"node_type": "course", "course": course2.id}},
                    {"id": None, "data": {"node_type": "course", "course": course3.id}},
                ],
            },
        ],
        context={"program": program},
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()

    root.refresh_from_db()
    assert ProgramRequirementTreeSerializer(instance=root).data == [
        {
            "data": {
                "node_type": "operator",
                "operator": "all_of",
                "operator_value": None,
                "program": program.id,
                "course": None,
                "required_program": None,
                "title": "Required Courses",
                "elective_flag": False,
            },
            "id": ANY,
            "children": [
                {
                    "data": {
                        "node_type": "course",
                        "operator": None,
                        "operator_value": None,
                        "program": program.id,
                        "course": course1.id,
                        "required_program": None,
                        "title": None,
                        "elective_flag": False,
                    },
                    "id": ANY,
                }
            ],
        },
        {
            "data": {
                "node_type": "operator",
                "operator": "min_number_of",
                "operator_value": "1",
                "program": program.id,
                "course": None,
                "required_program": None,
                "title": "Elective Courses",
                "elective_flag": False,
            },
            "id": ANY,
            "children": [
                {
                    "data": {
                        "node_type": "course",
                        "operator": None,
                        "operator_value": None,
                        "program": program.id,
                        "course": course2.id,
                        "required_program": None,
                        "title": None,
                        "elective_flag": False,
                    },
                    "id": ANY,
                },
                {
                    "data": {
                        "node_type": "course",
                        "operator": None,
                        "operator_value": None,
                        "program": program.id,
                        "course": course3.id,
                        "required_program": None,
                        "title": None,
                        "elective_flag": False,
                    },
                    "id": ANY,
                },
            ],
        },
    ]
