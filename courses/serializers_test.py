"""
Tests for course serializers
"""
# pylint: disable=unused-argument, redefined-outer-name
from datetime import timedelta
from decimal import Decimal

import bleach
import pytest
from django.contrib.auth.models import AnonymousUser
from django.utils.timezone import now

from cms.factories import CoursePageFactory, FlexiblePricingFormFactory
from cms.serializers import ProgramPageSerializer, CoursePageSerializer
from courses.factories import (
    CourseFactory,
    CourseRunEnrollmentFactory,
    CourseRunFactory,
    CourseRunGradeFactory,
    ProgramFactory,
    program_with_empty_requirements,
)
from courses.models import (
    Department,
    ProgramRequirement,
    ProgramRequirementNodeType,
)
from courses.serializers import (
    CourseSerializer,
    BaseCourseSerializer,
    BaseProgramSerializer,
    CourseRunWithCourseSerializer,
    CourseRunEnrollmentSerializer,
    CourseRunGradeSerializer,
    CourseRunSerializer,
    CourseWithCourseRunsSerializer,
    LearnerRecordSerializer,
    ProgramRequirementSerializer,
    ProgramRequirementTreeSerializer,
    ProgramSerializer,
)
from ecommerce.serializers import BaseProductSerializer
from flexiblepricing.constants import FlexiblePriceStatus
from flexiblepricing.factories import FlexiblePriceFactory
from main.test_utils import assert_drf_json_equal, drf_datetime
from main import features
from mitol.common.utils.datetime import now_in_utc
from openedx.constants import EDX_ENROLLMENT_AUDIT_MODE, EDX_ENROLLMENT_VERIFIED_MODE

pytestmark = [pytest.mark.django_db]


def test_base_program_serializer():
    """Test BaseProgramSerializer serialization"""
    program = ProgramFactory.create()
    data = BaseProgramSerializer(program).data
    assert data == {
        "title": program.title,
        "readable_id": program.readable_id,
        "id": program.id,
        "type": "program",
    }


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


def test_base_course_serializer():
    """Test CourseRun serialization"""
    course = CourseFactory.create()
    data = BaseCourseSerializer(course).data
    assert data == {
        "title": course.title,
        "readable_id": course.readable_id,
        "id": course.id,
        "type": "course",
    }


@pytest.mark.parametrize("is_anonymous", [True, False])
@pytest.mark.parametrize("all_runs", [True, False])
def test_serialize_course(mocker, mock_context, is_anonymous, all_runs, settings):
    """Test Course serialization"""
    settings.FEATURES[features.ENABLE_NEW_DESIGN] = True
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
            "programs": ProgramSerializer(course.programs, many=True).data
            if all_runs
            else None,
        },
    )


@pytest.mark.parametrize("financial_assistance_available", [True, False])
def test_serialize_course_with_page_fields(
    mocker, mock_context, financial_assistance_available
):
    """
    Tests course serialization with Page fields and Financial Assistance form.
    """
    fake_image_src = "http://example.com/my.img"
    patched_get_wagtail_src = mocker.patch(
        "cms.serializers.get_wagtail_img_src", return_value=fake_image_src
    )
    if financial_assistance_available:
        financial_assistance_form = FlexiblePricingFormFactory()
        course_page = financial_assistance_form.get_parent()
        course_page.product.program = None
        expected_financial_assistance_url = (
            f"{course_page.get_url()}{financial_assistance_form.slug}/"
        )
    else:
        course_page = CoursePageFactory.create()
        course_page.product.program = None
        expected_financial_assistance_url = ""
    course = course_page.course
    data = BaseCourseSerializer(
        instance=course, context={**mock_context, "include_page_fields": True}
    ).data
    assert_drf_json_equal(
        data,
        {
            "title": course.title,
            "readable_id": course.readable_id,
            "id": course.id,
            "type": "course",
            "feature_image_src": fake_image_src,
            "page_url": None,
            "financial_assistance_form_url": expected_financial_assistance_url,
            "instructors": [],
            "current_price": None,
            "description": bleach.clean(course_page.description, tags=[], strip=True),
            "live": True,
            "effort": course_page.effort,
            "length": course_page.length,
        },
    )
    patched_get_wagtail_src.assert_called_once_with(course_page.feature_image)


def test_serialize_course_run():
    """Test CourseRun serialization"""
    course_run = CourseRunFactory.create(course__page=None)
    course_run.refresh_from_db()

    data = CourseRunSerializer(course_run).data
    assert_drf_json_equal(
        data,
        {
            "title": course_run.title,
            "courseware_id": course_run.courseware_id,
            "run_tag": course_run.run_tag,
            "courseware_url": course_run.courseware_url,
            "start_date": drf_datetime(course_run.start_date),
            "end_date": drf_datetime(course_run.end_date),
            "enrollment_start": drf_datetime(course_run.enrollment_start),
            "enrollment_end": drf_datetime(course_run.enrollment_end),
            "expiration_date": drf_datetime(course_run.expiration_date),
            "upgrade_deadline": drf_datetime(course_run.upgrade_deadline),
            "is_upgradable": course_run.is_upgradable,
            "id": course_run.id,
            "products": [],
            "approved_flexible_price_exists": False,
            "live": True,
            "is_self_paced": course_run.is_self_paced,
            "certificate_available_date": drf_datetime(
                course_run.certificate_available_date
            ),
            "course_number": course_run.course_number,
        },
    )


def test_serialize_course_run_with_course():
    """Test CoursePageDepartmentsSerializer serialization"""
    course_run = CourseRunFactory.create(course__page=None)
    data = CourseRunWithCourseSerializer(course_run).data

    assert data == {
        "course": CourseSerializer(course_run.course).data,
        "course_number": course_run.course_number,
        "title": course_run.title,
        "courseware_id": course_run.courseware_id,
        "courseware_url": course_run.courseware_url,
        "start_date": drf_datetime(course_run.start_date),
        "end_date": drf_datetime(course_run.end_date),
        "enrollment_start": drf_datetime(course_run.enrollment_start),
        "enrollment_end": drf_datetime(course_run.enrollment_end),
        "expiration_date": drf_datetime(course_run.expiration_date),
        "upgrade_deadline": drf_datetime(course_run.upgrade_deadline),
        "certificate_available_date": drf_datetime(
            course_run.certificate_available_date
        ),
        "is_upgradable": course_run.is_upgradable,
        "is_self_paced": False,
        "id": course_run.id,
        "products": BaseProductSerializer(course_run.products, many=True).data,
        "approved_flexible_price_exists": False,
        "live": True,
        "run_tag": course_run.run_tag,
    }


@pytest.mark.parametrize("receipts_enabled", [True, False])
def test_serialize_course_run_enrollments(settings, receipts_enabled):
    """Test that CourseRunEnrollmentSerializer has correct data"""
    settings.ENABLE_ORDER_RECEIPTS = receipts_enabled
    course_run_enrollment = CourseRunEnrollmentFactory.create()
    serialized_data = CourseRunEnrollmentSerializer(course_run_enrollment).data
    assert serialized_data == {
        "run": CourseRunWithCourseSerializer(course_run_enrollment.run).data,
        "id": course_run_enrollment.id,
        "edx_emails_subscription": True,
        "enrollment_mode": "audit",
        "certificate": None,
        "approved_flexible_price_exists": False,
        "grades": [],
    }


@pytest.mark.parametrize("approved_flexible_price_exists", [True, False])
def test_serialize_course_run_enrollments_with_flexible_pricing(
    approved_flexible_price_exists,
):
    """Test that CourseRunEnrollmentSerializer has correct data"""
    course_run_enrollment = CourseRunEnrollmentFactory.create()
    if approved_flexible_price_exists:
        status = FlexiblePriceStatus.APPROVED
    else:
        status = FlexiblePriceStatus.PENDING_MANUAL_APPROVAL

    FlexiblePriceFactory.create(
        user=course_run_enrollment.user,
        courseware_object=course_run_enrollment.run.course,
        status=status,
    )
    serialized_data = CourseRunEnrollmentSerializer(course_run_enrollment).data
    assert serialized_data == {
        "run": CourseRunWithCourseSerializer(course_run_enrollment.run).data,
        "id": course_run_enrollment.id,
        "edx_emails_subscription": True,
        "enrollment_mode": "audit",
        "approved_flexible_price_exists": approved_flexible_price_exists,
        "certificate": None,
        "grades": [],
    }


def test_serialize_course_run_enrollments_with_grades():
    """Test that CourseRunEnrollmentSerializer has correct data"""
    course_run_enrollment = CourseRunEnrollmentFactory.create()

    grade = CourseRunGradeFactory.create(
        course_run=course_run_enrollment.run, user=course_run_enrollment.user
    )

    serialized_data = CourseRunEnrollmentSerializer(course_run_enrollment).data
    assert serialized_data == {
        "run": CourseRunWithCourseSerializer(course_run_enrollment.run).data,
        "id": course_run_enrollment.id,
        "edx_emails_subscription": True,
        "enrollment_mode": "audit",
        "approved_flexible_price_exists": False,
        "certificate": None,
        "grades": CourseRunGradeSerializer([grade], many=True).data,
    }


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
# @pytest.mark.parametrize(
#     "certificate_generated, certificate_available_date_ended, course_ended",
#     (
#         [True, False, False],
#         [False, True, False],
#         [False, False, True],
#     ),
# )
def test_learner_record_serializer(
    mock_context,
    program_with_empty_requirements,
    enrollment_mode,
    # certificate_generated,
    # certificate_available_date_ended,
    # course_ended,
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
