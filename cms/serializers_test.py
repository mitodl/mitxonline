"""
Tests for cms serializers
"""
from cms.factories import (
    CoursePageFactory,
    FlexiblePricingFormFactory,
    ProgramPageFactory,
)
from cms.serializers import CoursePageSerializer
from courses.factories import CourseFactory, ProgramFactory
from main.test_utils import assert_drf_json_equal


def test_serialize_course_page(mocker, mock_context):
    """
    Tests course page serialization with Financial Assistance form with a parent-child relationship
    with a course, but no program.
    """
    fake_image_src = "http://example.com/my.img"
    patched_get_wagtail_src = mocker.patch(
        "cms.serializers.get_wagtail_img_src", return_value=fake_image_src
    )

    financial_assistance_form = FlexiblePricingFormFactory()
    course_page = financial_assistance_form.get_parent()
    course_page.product.program = None

    data = CoursePageSerializer(instance=course_page).data
    assert_drf_json_equal(
        data,
        {
            "feature_image_src": fake_image_src,
            "page_url": None,
            "financial_assistance_form_url": f"{course_page.get_url()}{financial_assistance_form.slug}/",
        },
    )
    patched_get_wagtail_src.assert_called_once_with(course_page.feature_image)


def test_serialize_course_page_with_flex_price_with_program_fk(mocker, mock_context):
    """
    Tests course page serialization with Financial Assistance form which has a fk relationship to
    a program, but no parent-child relationship with any course or program.
    """
    fake_image_src = "http://example.com/my.img"
    mocker.patch("cms.serializers.get_wagtail_img_src", return_value=fake_image_src)

    program = ProgramFactory()
    program_page = ProgramPageFactory(program=program)
    financial_assistance_form = FlexiblePricingFormFactory(
        selected_program_id=program.id, parent=program_page
    )
    course = CourseFactory(program=program)
    course_page = CoursePageFactory(course=course)

    data = CoursePageSerializer(instance=course_page).data
    assert_drf_json_equal(
        data,
        {
            "feature_image_src": fake_image_src,
            "page_url": None,
            "financial_assistance_form_url": f"{program_page.get_url()}{financial_assistance_form.slug}/",
        },
    )


def test_serialize_course_page_with_flex_price_form_as_program_child(
    mocker, mock_context
):
    """
    Tests course page serialization with Financial Assistance form which has no fk relationship
    to a course or program, only a parent-child relationship with a program.
    """
    fake_image_src = "http://example.com/my.img"
    mocker.patch("cms.serializers.get_wagtail_img_src", return_value=fake_image_src)

    program = ProgramFactory()
    program_page = ProgramPageFactory(program=program)
    financial_assistance_form = FlexiblePricingFormFactory(parent=program_page)
    course = CourseFactory(program=program)
    course_page = CoursePageFactory(course=course)

    data = CoursePageSerializer(instance=course_page).data
    assert_drf_json_equal(
        data,
        {
            "feature_image_src": fake_image_src,
            "page_url": None,
            "financial_assistance_form_url": f"{program_page.get_url()}{financial_assistance_form.slug}/",
        },
    )


def test_serialize_course_page_with_flex_price_form_as_child_no_program(
    mocker, mock_context
):
    """
    Tests course page serialization with Financial Assistance form with a fk relationship with a course
    but no parent-child relationship with a course or program.
    """
    fake_image_src = "http://example.com/my.img"
    mocker.patch("cms.serializers.get_wagtail_img_src", return_value=fake_image_src)

    course = CourseFactory(program=None)
    course_page = CoursePageFactory(course=course)
    financial_assistance_form = FlexiblePricingFormFactory(
        selected_course_id=course.id, parent=course_page
    )

    data = CoursePageSerializer(instance=course_page).data
    assert_drf_json_equal(
        data,
        {
            "feature_image_src": fake_image_src,
            "page_url": None,
            "financial_assistance_form_url": f"{course_page.get_url()}{financial_assistance_form.slug}/",
        },
    )
