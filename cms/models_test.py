from unittest.mock import PropertyMock, create_autospec
from urllib.parse import quote_plus

import pytest
import factory
from django.contrib.auth.models import AnonymousUser
from django.urls import resolve
from django.test.client import RequestFactory
from mitol.common.factories import UserFactory

from cms.factories import ResourcePageFactory, CoursePageFactory
from courses.factories import CourseRunEnrollmentFactory, CourseRunFactory

pytestmark = [pytest.mark.django_db]

FAKE_READABLE_ID = "some:readable-id"


def test_resource_page_site_name(settings, mocker):
    """
    ResourcePage should include site_name in its context
    """
    settings.SITE_NAME = "a site's name"
    page = ResourcePageFactory.create()
    assert page.get_context(mocker.Mock())["site_name"] == settings.SITE_NAME


def test_custom_detail_page_urls(fully_configured_wagtail):
    """Verify that course detail pages return our custom URL path"""
    course_pages = CoursePageFactory.create_batch(
        2, course__readable_id=factory.Iterator([FAKE_READABLE_ID, "non-matching-id"])
    )
    assert course_pages[0].get_url() == "/courses/{}/".format(FAKE_READABLE_ID)


def test_custom_detail_page_urls_handled(fully_configured_wagtail):
    """Verify that custom URL paths for our course pages are served by the standard Wagtail view"""
    CoursePageFactory.create(course__readable_id=FAKE_READABLE_ID)
    resolver_match = resolve("/courses/{}/".format(FAKE_READABLE_ID))
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
    staff_user,
    fully_configured_wagtail,
    is_authenticated,
    has_unexpired_run,
    enrolled,
    exp_sign_in_url,
    exp_is_enrolled,
):
    """CoursePage.get_context should return expected values"""
    rf = RequestFactory()
    request = rf.get("/")
    request.user = staff_user if is_authenticated else AnonymousUser()
    if has_unexpired_run:
        run = CourseRunFactory.create(course__readable_id=FAKE_READABLE_ID)
        course_page_kwargs = dict(course=run.course)
    else:
        run = None
        course_page_kwargs = dict(course__readable_id=FAKE_READABLE_ID)
    course_page = CoursePageFactory.create(**course_page_kwargs)
    if enrolled:
        CourseRunEnrollmentFactory.create(user=staff_user, run=run)
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
        "can_access_edx_course": is_authenticated and has_unexpired_run,
    }


@pytest.mark.parametrize(
    "is_authed,is_editor,has_unexpired_run,is_in_progress,exp_can_access",
    [
        [True, True, True, True, True],
        [False, True, True, True, False],
        [True, True, True, False, True],
        [True, True, False, True, False],
        [True, False, True, False, False],
    ],
)
def test_course_page_context_edx_access(
    user,
    fully_configured_wagtail,
    is_authed,
    is_editor,
    has_unexpired_run,
    is_in_progress,
    exp_can_access,
):
    """CoursePage.get_context should correctly indicate if user can access the edX course"""
    if not is_authed:
        request_user = AnonymousUser()
    else:
        # Use a mock with a request user's properties copied over so we can set the 'is_editor' flag as we want
        mock_request_user = create_autospec(user, instance=True, **user.__dict__)
        mock_request_user.is_editor = is_editor
        request_user = mock_request_user
    rf = RequestFactory()
    request = rf.get("/")
    request.user = request_user
    course_page = CoursePageFactory.create(course__readable_id=FAKE_READABLE_ID)
    if has_unexpired_run:
        CourseRunFactory.create(
            course=course_page.course,
            **(dict(in_progress=True) if is_in_progress else dict(in_future=True)),
        )
    context = course_page.get_context(request=request)
    assert context["can_access_edx_course"] is exp_can_access
