"""Tests for CMS app API functionality"""
import pytest
from django.contrib.contenttypes.models import ContentType
from wagtail.core.models import Page

from cms.api import ensure_home_page_and_site, get_wagtail_img_src, ensure_resource_pages
from cms.factories import HomePageFactory
from cms.models import HomePage, ResourcePage

pytestmark = [pytest.mark.django_db]


@pytest.mark.django_db
def test_ensure_home_page_and_site():
    """
    ensure_home_page_and_site should make sure that a home page is created if one doesn't exist, it is set to be
    a child of the root, and the default Wagtail page is deleted.
    """
    home_page_qset = Page.objects.filter(
        content_type=ContentType.objects.get_for_model(HomePage)
    )
    wagtail_default_page_qset = Page.objects.filter(
        depth=2, content_type=ContentType.objects.get_for_model(Page)
    )
    assert home_page_qset.exists() is False
    assert wagtail_default_page_qset.exists() is True
    ensure_home_page_and_site()
    assert wagtail_default_page_qset.exists() is False
    home_page = home_page_qset.first()
    assert home_page is not None
    home_page_parents = home_page.get_ancestors()
    assert home_page_parents.count() == 1
    assert home_page_parents.first().is_root() is True


@pytest.mark.django_db
def test_get_wagtail_img_src(settings):
    """get_wagtail_img_src should return the correct image URL"""
    settings.MEDIA_URL = "/mediatest/"
    img_path = "/path/to/my-image.jpg"
    img_hash = "abc123"
    home_page = HomePageFactory.build(
        hero__file__filename=img_path, hero__file_hash=img_hash
    )
    img_src = get_wagtail_img_src(home_page.hero)
    assert img_src == f"{img_path}?v={img_hash}"


@pytest.mark.django_db
def test_ensure_resource_pages():
    """
    ensure_resource_pages makes sure that resource pages created if no already exist
    """
    ensure_home_page_and_site()
    resource_page_qset = Page.objects.filter(
        content_type=ContentType.objects.get_for_model(ResourcePage)
    )
    assert not resource_page_qset.exists()
    assert resource_page_qset.count() == 0
    ensure_resource_pages()
    assert resource_page_qset.exists()
    assert resource_page_qset.count() == 4
    assert ResourcePage.objects.filter(title='About Us').exists()
    assert ResourcePage.objects.filter(title='Terms of Service').exists()
    assert ResourcePage.objects.filter(title='Privacy Policy').exists()
    assert ResourcePage.objects.filter(title='Honor Code').exists()
