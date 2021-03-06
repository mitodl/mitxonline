"""Tests for Wagtail models"""
from urllib.parse import quote_plus

import pytest
import factory
import json
from django.contrib.auth.models import AnonymousUser, Group
from django.urls import resolve
from django.test.client import RequestFactory
from mitol.common.factories import UserFactory
from django.contrib.sessions.middleware import SessionMiddleware

from cms.constants import CMS_EDITORS_GROUP_NAME
from cms.factories import (
    ResourcePageFactory,
    CoursePageFactory,
    FlexiblePricingFormFactory,
)
from cms.models import FlexiblePricingRequestSubmission
from courses.factories import CourseRunEnrollmentFactory, CourseRunFactory
from flexiblepricing.models import FlexiblePrice
from flexiblepricing.constants import FlexiblePriceStatus

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
    "is_authenticated,has_relevant_run,enrolled,exp_sign_in_url,exp_is_enrolled",
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
    has_relevant_run,
    enrolled,
    exp_sign_in_url,
    exp_is_enrolled,
):
    """CoursePage.get_context should return expected values"""
    rf = RequestFactory()
    request = rf.get("/")
    request.user = staff_user if is_authenticated else AnonymousUser()
    if has_relevant_run:
        run = CourseRunFactory.create(
            course__readable_id=FAKE_READABLE_ID, in_future=True
        )
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
        "can_access_edx_course": is_authenticated and has_relevant_run,
    }


@pytest.mark.parametrize(
    "is_authed,is_editor,has_relevant_run,is_in_progress,exp_can_access",
    [
        [True, True, True, True, True],
        [False, False, True, True, False],
        [True, True, True, False, True],
        [True, True, False, True, False],
        [True, False, True, False, False],
    ],
)
def test_course_page_context_edx_access(
    mocker,
    fully_configured_wagtail,
    is_authed,
    is_editor,
    has_relevant_run,
    is_in_progress,
    exp_can_access,
):
    """CoursePage.get_context should correctly indicate if user can access the edX course"""
    course_page = CoursePageFactory.create(course__readable_id=FAKE_READABLE_ID)
    run = (
        None
        if not has_relevant_run
        else CourseRunFactory.create(
            course=course_page.course,
            **(dict(in_progress=True) if is_in_progress else dict(in_future=True)),
        )
    )
    patched_get_relevant_run = mocker.patch(
        "cms.models.get_user_relevant_course_run", return_value=run
    )
    if not is_authed:
        request_user = AnonymousUser()
    else:
        request_user = UserFactory.create()
    if is_editor:
        editor_group = Group.objects.get(name=CMS_EDITORS_GROUP_NAME)
        editor_group.user_set.add(request_user)
        request_user.save()
    rf = RequestFactory()
    request = rf.get("/")
    request.user = request_user
    context = course_page.get_context(request=request)
    assert context["can_access_edx_course"] is exp_can_access
    patched_get_relevant_run.assert_called_once_with(
        course=course_page.course, user=request_user
    )


def generate_flexible_pricing_response(request_user, flexible_pricing_form):
    """
    Generates a fully realized request for the Flexible Pricing tests.

    Args:
        request_user    User object to use for authentication
        flexible_pricing_form   The factory-generated form object

    Returns:
        TemplateResponse - this will call render() for you
    """
    rf = RequestFactory()
    request = rf.get("/")
    request.user = request_user

    middleware = SessionMiddleware()
    middleware.process_request(request)
    request.session.save()

    response = flexible_pricing_form.serve(request)
    response.render()

    assert response.is_rendered

    return response


@pytest.mark.parametrize(
    "is_authed,has_submission", [[False, False], [True, False], [True, True]]
)
def test_flex_pricing_form_display(mocker, is_authed, has_submission):
    """
    Tests the initial display of the flexible pricing form. If the user is not
    authenticated, they should see the guest text. If they are, they should
    see the form if they don't have an in-progress submission.
    """
    course_page = CoursePageFactory.create(course__readable_id=FAKE_READABLE_ID)
    flex_form = FlexiblePricingFormFactory()

    if not is_authed:
        request_user = AnonymousUser()
    else:
        request_user = UserFactory.create()
        if has_submission:
            submission = FlexiblePricingRequestSubmission.objects.create(
                form_data=json.dumps([]), page=flex_form, user=request_user
            )
            flexprice = FlexiblePrice.objects.create(
                user=request_user,
                cms_submission=submission,
                courseware_object=course_page.course,
            )

    response = generate_flexible_pricing_response(request_user, flex_form)

    # simple string checking for the rendered content
    # should match what's in the factory

    if not is_authed:
        assert "Not Logged In" in response.rendered_content
    else:
        if has_submission:
            assert "Application Processing" in response.rendered_content
        else:
            assert "csrfmiddlewaretoken" in response.rendered_content


@pytest.mark.parametrize(
    "submission_status",
    [
        [FlexiblePriceStatus.CREATED],
        [FlexiblePriceStatus.APPROVED],
        [FlexiblePriceStatus.SKIPPED],
    ],
)
def test_flex_pricing_form_state_display(mocker, submission_status):
    """
    Tests the display when the user goes to submit a request again - they should
    get one of three status update pages instead of the form.
    """

    course_page = CoursePageFactory.create(course__readable_id=FAKE_READABLE_ID)
    flex_form = FlexiblePricingFormFactory()

    request_user = UserFactory.create()
    submission = FlexiblePricingRequestSubmission.objects.create(
        form_data=json.dumps([]), page=flex_form, user=request_user
    )
    flexprice = FlexiblePrice.objects.create(
        user=request_user,
        cms_submission=submission,
        status=submission_status,
        courseware_object=course_page.course,
    )

    response = generate_flexible_pricing_response(request_user, flex_form)

    if submission_status == FlexiblePriceStatus.CREATED:
        assert "Application Processing" in response.rendered_content
    elif submission_status == FlexiblePriceStatus.APPROVED:
        assert "Application Approved" in response.rendered_content
    elif submission_status == FlexiblePriceStatus.SKIPPED:
        assert "Application Denied" in response.rendered_content
