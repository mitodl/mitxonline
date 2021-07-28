"""Tests for CMS template tags"""
from wagtail_factories import ImageFactory

from cms.templatetags.wagtail_img_src import wagtail_img_src


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
