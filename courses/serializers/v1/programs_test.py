import pytest
from datetime import timedelta
from decimal import Decimal

from django.utils.timezone import now
from mitol.common.utils import now_in_utc

from cms.serializers import ProgramPageSerializer
from courses.factories import (
    CourseRunFactory,
    ProgramFactory,
    CourseFactory,
    CourseRunEnrollmentFactory,
    CourseRunGradeFactory,
    program_with_empty_requirements,
)
from courses.models import Department, ProgramRequirementNodeType, ProgramRequirement
from courses.serializers.v1.courses import CourseWithCourseRunsSerializer
from courses.serializers.v1.programs import (
    ProgramSerializer,
    LearnerRecordSerializer,
    ProgramRequirementSerializer,
    ProgramRequirementTreeSerializer,
)
from main.test_utils import assert_drf_json_equal
from openedx.constants import EDX_ENROLLMENT_VERIFIED_MODE, EDX_ENROLLMENT_AUDIT_MODE

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
    runs = (
        [run1, run2]
        + [
            CourseRunFactory.create(
                course=course1, start_date=now() + timedelta(hours=3)
            )
            for _ in range(2)
        ]
        + [
            CourseRunFactory.create(
                course=course2, start_date=now() + timedelta(hours=3)
            )
            for _ in range(2)
        ]
    )
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
            "courses": [
                CourseWithCourseRunsSerializer(
                    instance=course, context={**mock_context}
                ).data
                for course in [course1, course2]
            ]
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


def test_program_requirement_tree_serializer_valid():
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
                "children": [],
            },
        ],
        context={"program": program},
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()


def test_program_requirement_deletion():
    """Verify that saving the requirements for one program doesn't affect other programs"""

    courses = CourseFactory.create_batch(3)

    program1 = ProgramFactory.create()
    program2 = ProgramFactory.create()
    root1 = program1.requirements_root
    root2 = program2.requirements_root

    for root in [root1, root2]:
        program = root.program
        # build the same basic tree structure for both
        required = root.add_child(
            program=program,
            node_type=ProgramRequirementNodeType.OPERATOR,
            title="Required",
            operator=ProgramRequirement.Operator.ALL_OF,
        )
        for course in courses:
            required.add_child(
                program=program,
                node_type=ProgramRequirementNodeType.COURSE,
                course=course,
            )

    expected = list(ProgramRequirement.get_tree(parent=root2))

    # this will delete everything under this tree
    serializer = ProgramRequirementTreeSerializer(instance=root1, data=[])
    serializer.is_valid(raise_exception=True)
    serializer.save()

    assert list(ProgramRequirement.get_tree(parent=root1)) == [
        root1
    ]  # just the one root node
    assert list(ProgramRequirement.get_tree(parent=root2)) == expected


@pytest.mark.parametrize(
    "enrollment_mode", [EDX_ENROLLMENT_VERIFIED_MODE, EDX_ENROLLMENT_AUDIT_MODE]
)
def test_learner_record_serializer(
    mock_context, program_with_empty_requirements, enrollment_mode
):
    """Verify that saving the requirements for one program doesn't affect other programs"""

    program = program_with_empty_requirements
    courses = CourseFactory.create_batch(3)

    user = mock_context["request"].user

    course_runs = []
    grades = []
    grade_multiplier_to_test_ordering = 1
    for course in courses:
        program.add_requirement(course)
        course_run = CourseRunFactory.create(course=course)
        course_run_enrollment = CourseRunEnrollmentFactory.create(
            run=course_run,
            user=user,
            enrollment_mode=enrollment_mode,
        )
        course_runs.append(course_run)

        grades.append(
            CourseRunGradeFactory.create(
                course_run=course_run,
                user=user,
                grade=(0.313133 * grade_multiplier_to_test_ordering),
            )
        )
        grade_multiplier_to_test_ordering += 1

    serialized_data = LearnerRecordSerializer(
        instance=program, context=mock_context
    ).data
    program_requirements_payload = [
        {
            "children": [
                {
                    "children": [
                        {
                            "data": {
                                "course": courses[0].id,
                                "node_type": "course",
                                "operator": None,
                                "operator_value": None,
                                "program": program.id,
                                "title": "",
                                "elective_flag": False,
                            },
                            "id": program.get_requirements_root()
                            .get_children()
                            .first()
                            .get_children()
                            .filter(course=courses[0].id)
                            .first()
                            .id,
                        },
                        {
                            "data": {
                                "course": courses[1].id,
                                "node_type": "course",
                                "operator": None,
                                "operator_value": None,
                                "program": program.id,
                                "title": "",
                                "elective_flag": False,
                            },
                            "id": program.get_requirements_root()
                            .get_children()
                            .first()
                            .get_children()
                            .filter(course=courses[1].id)
                            .first()
                            .id,
                        },
                        {
                            "data": {
                                "course": courses[2].id,
                                "node_type": "course",
                                "operator": None,
                                "operator_value": None,
                                "program": program.id,
                                "title": "",
                                "elective_flag": False,
                            },
                            "id": program.get_requirements_root()
                            .get_children()
                            .first()
                            .get_children()
                            .filter(course=courses[2].id)
                            .first()
                            .id,
                        },
                    ],
                    "data": {
                        "course": None,
                        "node_type": "operator",
                        "operator": ProgramRequirement.Operator.ALL_OF.value,
                        "operator_value": None,
                        "program": program.id,
                        "title": "Required Courses",
                        "elective_flag": False,
                    },
                    "id": program.get_requirements_root().get_children().first().id,
                },
                {
                    "data": {
                        "course": None,
                        "node_type": "operator",
                        "operator": ProgramRequirement.Operator.MIN_NUMBER_OF.value,
                        "operator_value": "1",
                        "program": program.id,
                        "title": "Elective Courses",
                        "elective_flag": True,
                    },
                    "id": program.get_requirements_root().get_children().last().id,
                },
            ],
            "data": {
                "course": None,
                "node_type": "program_root",
                "operator": None,
                "operator_value": None,
                "program": program.id,
                "title": "",
                "elective_flag": False,
            },
            "id": program.requirements_root.id,
        }
    ]
    user_info_payload = {
        "email": user.email,
        "name": user.name,
        "username": user.username,
    }
    course_0_payload = {
        "certificate": None,
        "grade": {
            "grade": round(grades[0].grade, 2),
            "grade_percent": Decimal(grades[0].grade_percent),
            "letter_grade": grades[0].letter_grade,
            "passed": grades[0].passed,
            "set_by_admin": grades[0].set_by_admin,
        },
        "id": courses[0].id,
        "readable_id": courses[0].readable_id,
        "reqtype": "Required Courses",
        "title": courses[0].title,
    }
    if enrollment_mode == EDX_ENROLLMENT_AUDIT_MODE:
        course_0_payload["grade"] = None
    if course_runs[0].certificate_available_date >= now_in_utc() or (
        not course_runs[0].certificate_available_date
        and course_runs[0].end_date >= now_in_utc()
    ):
        course_0_payload["grade"] = None
    assert user_info_payload == serialized_data["user"]
    assert program_requirements_payload == serialized_data["program"]["requirements"]
    assert course_0_payload == serialized_data["program"]["courses"][0]


def test_program_serializer_returns_default_image():
    """If the program has no page, we should still get a featured_image_url."""

    program = ProgramFactory.create(page=None)

    assert "feature_image_src" in ProgramSerializer(program).data["page"]


@pytest.mark.parametrize(
    "data",
    [
        {
            "id": None,
            "data": {
                "node_type": ProgramRequirementNodeType.COURSE,
            },
            "children": [],
        },
        {
            "id": 1,
            "data": {
                "node_type": ProgramRequirementNodeType.COURSE,
            },
            "children": [],
        },
        {
            "id": 1,
            "data": {
                "node_type": ProgramRequirementNodeType.COURSE,
            },
        },
        {
            "data": {
                "node_type": ProgramRequirementNodeType.COURSE,
            },
            "children": [],
        },
    ],
)
def test_program_requirement_serializer_valid(data):
    """Verify that the ProgramRequirementSerializer validates data"""
    serializer = ProgramRequirementSerializer(data=data)
    serializer.is_valid(raise_exception=True)
