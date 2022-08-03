"""
Tests for cms serializers
"""
from cms.factories import FlexiblePricingFormFactory
from cms.serializers import CoursePageSerializer
from main.test_utils import assert_drf_json_equal


def test_serialize_course_page(mocker, mock_context):
    """
    Tests course page serialization with Financial Assistance form.
    """
    fake_image_src = "http://example.com/my.img"
    patched_get_wagtail_src = mocker.patch(
        "cms.serializers.get_wagtail_img_src", return_value=fake_image_src
    )

    financial_assistance_form = FlexiblePricingFormFactory()
    course_page = financial_assistance_form.get_parent()

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
