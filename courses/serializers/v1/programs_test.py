from datetime import timedelta
from decimal import Decimal
from unittest.mock import ANY

import pytest
from django.contrib.auth.models import AnonymousUser
from django.utils.timezone import now
from mitol.common.utils import now_in_utc
from rest_framework.exceptions import ValidationError

from cms.serializers import ProgramPageSerializer
from courses.factories import (
    CourseFactory,
    CourseRunCertificateFactory,
    CourseRunEnrollmentFactory,
    CourseRunFactory,
    CourseRunGradeFactory,
    EnrollmentModeFactory,
    LearnerProgramRecordShareFactory,
    PartnerSchoolFactory,
    ProgramFactory,
    program_with_empty_requirements,  # noqa: F401
    program_with_requirements,  # noqa: F401
)
from courses.models import Department, ProgramRequirement, ProgramRequirementNodeType
from courses.serializers.v1.courses import CourseWithCourseRunsSerializer
from courses.serializers.v1.programs import (
    LearnerRecordSerializer,
    ProgramRequirementSerializer,
    ProgramRequirementTreeSerializer,
    ProgramSerializer,
)
from main.test_utils import assert_drf_json_equal
from openedx.constants import EDX_ENROLLMENT_AUDIT_MODE, EDX_ENROLLMENT_VERIFIED_MODE
from users.factories import UserFactory

pytestmark = [pytest.mark.django_db]


@pytest.mark.parametrize(
    "remove_tree",
    [True, False],
)
def test_serialize_program(mock_context, remove_tree, program_with_empty_requirements):  # noqa: F811
    """Test Program serialization"""

    def sort_course_runs(course):
        """
        Sort course runs and enrollment modes in place to ensure consistent ordering for test assertions
        """
        course["courseruns"].sort(key=lambda cr: cr["id"])
        for course_run in course["courseruns"]:
            course_run["enrollment_modes"].sort(key=lambda em: em["mode_slug"])

    run1 = CourseRunFactory.create(
        course__page=None,
        start_date=now() + timedelta(hours=1),
    )
    run1.enrollment_modes.add(
        EnrollmentModeFactory.create(mode=EDX_ENROLLMENT_VERIFIED_MODE)
    )
    course1 = run1.course
    run2 = CourseRunFactory.create(
        course__page=None,
        start_date=now() + timedelta(hours=2),
    )
    run2.enrollment_modes.add(
        EnrollmentModeFactory.create(mode=EDX_ENROLLMENT_VERIFIED_MODE)
    )
    course2 = run2.course
    runs = (  # noqa: F841
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

    expected_courses = (
        [
            CourseWithCourseRunsSerializer(
                instance=course, context={**mock_context}
            ).data
            for course in [course1, course2]
        ]
        if not remove_tree
        else []
    )

    # Sort course runs and enrollment modes in expected data and actual data to ensure consistent ordering for assertions
    for course in expected_courses:
        sort_course_runs(course)

    for course in data["courses"]:
        sort_course_runs(course)

    assert_drf_json_equal(
        data,
        {
            "title": program_with_empty_requirements.title,
            "readable_id": program_with_empty_requirements.readable_id,
            "id": program_with_empty_requirements.id,
            "courses": expected_courses,
            "requirements": formatted_reqs,
            "req_tree": ProgramRequirementTreeSerializer(
                program_with_empty_requirements.requirements_root
            ).data,
            "page": ProgramPageSerializer(program_with_empty_requirements.page).data,
            "program_type": "Series",
            "departments": [],
            "live": True,
            "enrollment_modes": [],
        },
    )


def test_program_requirement_tree_serializer_save():
    """Verify that the ProgramRequirementTreeSerializer validates data"""
    program = ProgramFactory.create()
    course1, _course2, _course3 = CourseFactory.create_batch(3)
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

    root.refresh_from_db()
    assert ProgramRequirementTreeSerializer(instance=root).data == [
        {
            "data": {
                "node_type": "program_root",
                "operator": None,
                "operator_value": None,
                "program": program.id,
                "course": None,
                "required_program": None,
                "title": "",
                "elective_flag": False,
            },
            "id": ANY,
            "children": [
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
                },
            ],
        }
    ]


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
    mock_context,
    program_with_empty_requirements,  # noqa: F811
    enrollment_mode,
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
        course_run_enrollment = CourseRunEnrollmentFactory.create(  # noqa: F841
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
                                "required_program": None,
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
                                "required_program": None,
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
                                "required_program": None,
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
                        "required_program": None,
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
                        "required_program": None,
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
                "required_program": None,
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
        "username": user.edx_username,
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


def test_learner_record_serializer_raises_without_user(program_with_empty_requirements):  # noqa: F811
    """Raises ValidationError when context contains no valid user."""
    with pytest.raises(ValidationError):
        _ = LearnerRecordSerializer(program_with_empty_requirements, context={}).data


def test_learner_record_serializer_raises_with_anonymous_user(
    mocker, program_with_empty_requirements  # noqa: F811
):
    """Raises ValidationError when the request user is anonymous."""
    context = {"request": mocker.Mock(user=AnonymousUser())}
    with pytest.raises(ValidationError):
        _ = LearnerRecordSerializer(program_with_empty_requirements, context=context).data


def test_learner_record_serializer_user_from_context_key(program_with_empty_requirements):  # noqa: F811
    """User passed via context['user'] is used when no request is present."""
    user = UserFactory()
    data = LearnerRecordSerializer(
        program_with_empty_requirements, context={"user": user}
    ).data
    assert data["user"]["email"] == user.email
    assert data["user"]["name"] == user.name
    assert data["user"]["username"] == user.edx_username


def test_learner_record_serializer_anonymous_pull_hides_sharing_and_partners(
    program_with_empty_requirements,  # noqa: F811
):
    """anonymous_pull context causes sharing and partner_schools to be empty."""
    program = program_with_empty_requirements
    user = UserFactory()
    LearnerProgramRecordShareFactory(user=user, program=program, is_active=True)
    PartnerSchoolFactory()
    data = LearnerRecordSerializer(
        program, context={"user": user, "anonymous_pull": True}
    ).data
    assert data["sharing"] == []
    assert data["partner_schools"] == []


def test_learner_record_serializer_with_certificate(program_with_empty_requirements):  # noqa: F811
    """Grade and certificate are populated for a course with a non-revoked certificate."""
    program = program_with_empty_requirements
    user = UserFactory()
    course = CourseFactory()
    program.add_requirement(course)
    course_run = CourseRunFactory(course=course)
    certificate = CourseRunCertificateFactory(user=user, course_run=course_run)
    grade = CourseRunGradeFactory(user=user, course_run=course_run, grade=0.85)

    data = LearnerRecordSerializer(program, context={"user": user}).data
    course_data = data["program"]["courses"][0]

    assert course_data["certificate"] == {
        "uuid": str(certificate.uuid),
        "link": certificate.link,
    }
    assert course_data["grade"]["grade"] == round(grade.grade, 2)


def test_learner_record_serializer_revoked_certificate_excluded(
    program_with_empty_requirements,  # noqa: F811
):
    """A revoked certificate does not contribute to grade or certificate output."""
    program = program_with_empty_requirements
    user = UserFactory()
    course = CourseFactory()
    program.add_requirement(course)
    course_run = CourseRunFactory(course=course)
    CourseRunCertificateFactory(user=user, course_run=course_run, is_revoked=True)
    CourseRunGradeFactory(user=user, course_run=course_run)

    data = LearnerRecordSerializer(program, context={"user": user}).data
    course_data = data["program"]["courses"][0]

    assert course_data["certificate"] is None
    assert course_data["grade"] is None


def test_learner_record_serializer_highest_grade_selected(
    program_with_empty_requirements,  # noqa: F811
):
    """When a course has certificates on multiple runs, the highest grade is shown."""
    program = program_with_empty_requirements
    user = UserFactory()
    course = CourseFactory()
    program.add_requirement(course)
    run_low = CourseRunFactory(course=course)
    run_high = CourseRunFactory(course=course)
    CourseRunCertificateFactory(user=user, course_run=run_low)
    CourseRunCertificateFactory(user=user, course_run=run_high)
    CourseRunGradeFactory(user=user, course_run=run_low, grade=0.5)
    high_grade = CourseRunGradeFactory(user=user, course_run=run_high, grade=0.9)

    data = LearnerRecordSerializer(program, context={"user": user}).data
    course_data = data["program"]["courses"][0]

    assert course_data["grade"]["grade"] == round(high_grade.grade, 2)


def test_learner_record_serializer_sharing_and_partner_schools(
    program_with_empty_requirements,  # noqa: F811
):
    """Active shares appear in sharing; inactive shares do not. All partner schools appear."""
    program = program_with_empty_requirements
    user = UserFactory()
    active_share = LearnerProgramRecordShareFactory(
        user=user, program=program, is_active=True
    )
    LearnerProgramRecordShareFactory(user=user, program=program, is_active=False)
    school = PartnerSchoolFactory()

    data = LearnerRecordSerializer(program, context={"user": user}).data

    sharing_uuids = [str(s["share_uuid"]) for s in data["sharing"]]
    assert str(active_share.share_uuid) in sharing_uuids
    assert len(data["sharing"]) == 1
    school_ids = [s["id"] for s in data["partner_schools"]]
    assert school.id in school_ids


def test_program_serializer_returns_null_image_when_no_page():
    """If the program has no page, feature_image_src should be None (null)."""

    program = ProgramFactory.create(page=None)
    page_data = ProgramSerializer(program).data["page"]

    assert "feature_image_src" in page_data
    assert page_data["feature_image_src"] is None


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
