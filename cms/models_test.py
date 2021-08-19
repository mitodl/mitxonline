from urllib.parse import quote_plus

import pytest
import factory
from django.contrib.auth.models import AnonymousUser
from django.urls import resolve
from django.test.client import RequestFactory

from cms.factories import ResourcePageFactory, CoursePageFactory
from courses.factories import CourseRunEnrollmentFactory, CourseRunFactory

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


@pytest.mark.parametrize(
    "is_authenticated,has_unexpired_run,enrolled,exp_sign_in_url,exp_is_enrolled",
    [
        [True, True, True, False, True],
        [False, False, False, True, False],
        [False, True, True, True, False],
    ],
)
def test_course_page_context(
    user,
    is_authenticated,
    has_unexpired_run,
    enrolled,
    exp_sign_in_url,
    exp_is_enrolled,
):
    """CoursePage.get_context should return expected values"""
    rf = RequestFactory()
    request = rf.get("/")
    request.user = user if is_authenticated else AnonymousUser()
    course_readable_id = "my:course+1"
    if has_unexpired_run:
        run = CourseRunFactory.create(course__readable_id=course_readable_id)
        course_page_kwargs = dict(course=run.course)
    else:
        run = None
        course_page_kwargs = dict(course__readable_id=course_readable_id)
    course_page = CoursePageFactory.create(**course_page_kwargs)
    if enrolled:
        CourseRunEnrollmentFactory.create(user=user, run=run)
    context = course_page.get_context(request=request)
    assert context == {
        "self": course_page,
        "page": course_page,
        "request": request,
        "run": run,
        "is_enrolled": exp_is_enrolled,
        "sign_in_url": f"/signin/?next={quote_plus(course_page.get_url())}"
        if exp_sign_in_url
        else None,
        "start_date": getattr(run, "start_date", None),
    }
