"""Tests for CMS template tags"""
import pytest
from wagtail_factories import ImageFactory

from cms.factories import CoursePageFactory
from cms.templatetags.wagtail_img_src import wagtail_img_src
from cms.templatetags.feature_img_src import feature_img_src
from courses.constants import DEFAULT_COURSE_IMG_PATH


def test_wagtail_img_src(mocker, settings):
    """wagtail_img_src should use an API method to return the correct image URL"""
    image = ImageFactory.build()
    fake_src_value = "http://example.com"
    patched_get_src = mocker.patch(
        "cms.templatetags.wagtail_img_src.get_wagtail_img_src",
        return_value=fake_src_value,
    )
    img_src = wagtail_img_src(image)
    assert img_src == fake_src_value
    patched_get_src.assert_called_once_with(image)


@pytest.mark.django_db
def test_featured_img_src(mocker, settings):
    """featured_img_src should return the correct image URL if found else return the Default one"""
    image = ImageFactory()
    product = CoursePageFactory.create(
        feature_image=image
    )
    fake_src_value = "http://example.com"
    mocker.patch(
        "cms.templatetags.feature_img_src.get_wagtail_img_src",
        return_value=fake_src_value,
    )
    img_src = feature_img_src(product.feature_image)
    assert img_src == fake_src_value

    # Now when feature_image is not set.
    img_src = feature_img_src(None)
    assert img_src == '/static/' + DEFAULT_COURSE_IMG_PATH
