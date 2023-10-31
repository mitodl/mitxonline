import bleach
import pytest
from django.contrib.auth.models import AnonymousUser

from cms.factories import FlexiblePricingFormFactory, CoursePageFactory
from cms.serializers import CoursePageSerializer
from courses.factories import CourseRunFactory, CourseRunEnrollmentFactory, CourseRunGradeFactory
from courses.models import Department
from courses.serializers.v1.base import BaseCourseSerializer, CourseRunGradeSerializer
from courses.serializers.v1.courses import CourseRunSerializer, CourseWithCourseRunsSerializer, CourseSerializer, \
    CourseRunWithCourseSerializer, CourseRunEnrollmentSerializer
from courses.serializers.v1.programs import ProgramSerializer
from ecommerce.serializers import BaseProductSerializer
from flexiblepricing.constants import FlexiblePriceStatus
from flexiblepricing.factories import FlexiblePriceFactory
from main import features
from main.test_utils import assert_drf_json_equal, drf_datetime

pytestmark = [pytest.mark.django_db]


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
