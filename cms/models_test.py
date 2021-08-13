import pytest
import factory
from django.urls import resolve

from cms.factories import ResourcePageFactory, CoursePageFactory

pytestmark = [pytest.mark.django_db]


def test_resource_page_site_name(settings, mocker):
    """
    ResourcePage should include site_name in its context
    """
    settings.SITE_NAME = "a site's name"
    page = ResourcePageFactory.create()
    assert page.get_context(mocker.Mock())["site_name"] == settings.SITE_NAME


def test_custom_detail_page_urls():
    """Verify that course detail pages return our custom URL path"""
    readable_id = "some:readable-id"
    course_pages = CoursePageFactory.create_batch(
        2, course__readable_id=factory.Iterator([readable_id, "non-matching-id"])
    )
    assert course_pages[0].get_url() == "/courses/{}/".format(readable_id)


def test_custom_detail_page_urls_handled():
    """Verify that custom URL paths for our course pages are served by the standard Wagtail view"""
    readable_id = "some:readable-id"
    CoursePageFactory.create(course__readable_id=readable_id)
    resolver_match = resolve("/courses/{}/".format(readable_id))
    assert (
        resolver_match.func.__module__ == "wagtail.core.views"
    )  # pylint: disable=protected-access
    assert resolver_match.func.__name__ == "serve"  # pylint: disable=protected-access
