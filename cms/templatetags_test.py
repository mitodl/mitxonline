"""Tests for CMS template tags"""
import pytest

from cms.factories import HomePageFactory
from cms.templatetags.wagtail_img_src import wagtail_img_src


@pytest.mark.django_db
def test_wagtail_img_src(settings):
    """wagtail_img_src should return the correct image URL"""
    settings.MEDIA_URL = "/mediatest/"
    img_path = "/path/to/my-image.jpg"
    img_hash = "abc123"
    home_page = HomePageFactory.build(
        hero__file__filename=img_path, hero__file_hash=img_hash
    )
    img_src = wagtail_img_src(home_page.hero)
    assert img_src == f"{img_path}?v={img_hash}"
