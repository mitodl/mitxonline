"""Tests for Wagtail models"""
import json
from urllib.parse import quote_plus

import factory
import pytest
from django.conf import settings
from django.contrib.auth.models import AnonymousUser, Group
from django.contrib.sessions.middleware import SessionMiddleware
from django.test.client import RequestFactory
from django.urls import resolve
from mitol.common.factories import UserFactory

from cms.constants import CMS_EDITORS_GROUP_NAME
from cms.factories import (
    CoursePageFactory,
    FlexiblePricingFormFactory,
    ProgramPageFactory,
    ResourcePageFactory,
)
from cms.models import CoursePage, FlexiblePricingRequestSubmission, ProgramPage
from courses.factories import (
    CourseFactory,
    CourseRunEnrollmentFactory,
    CourseRunFactory,
    ProgramFactory,
)
from courses.models import CourseRun
from ecommerce.constants import DISCOUNT_TYPE_FIXED_PRICE
from ecommerce.factories import ProductFactory
from flexiblepricing.api import determine_courseware_flexible_price_discount
from flexiblepricing.constants import FlexiblePriceStatus
from flexiblepricing.factories import FlexiblePriceFactory, FlexiblePriceTierFactory
from flexiblepricing.models import FlexiblePrice
from main import features

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
    "is_authenticated,has_relevant_run,enrolled,exp_sign_in_url,exp_is_enrolled,has_finaid",
    [
        [True, True, True, False, True, True],
        [True, True, True, False, True, False],
        [False, False, False, True, False, False],
        [False, True, True, True, False, False],
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
    has_finaid,
):
    """CoursePage.get_context should return expected values"""
    rf = RequestFactory()
    request = rf.get("/")
    request.user = staff_user if is_authenticated else AnonymousUser()
    if has_relevant_run:
        run = CourseRunFactory.create(
            course__page=None, course__readable_id=FAKE_READABLE_ID, in_future=True
        )
        course_page_kwargs = dict(course=run.course)
    else:
        run = None
        course_page_kwargs = dict(course__readable_id=FAKE_READABLE_ID)
    if has_finaid and is_authenticated and has_relevant_run:
        sub = FlexiblePriceFactory(
            courseware_object=run.course,
            user=staff_user,
            status=FlexiblePriceStatus.APPROVED,
        )
        ProductFactory.create(purchasable_object=run)
        ecommerce_product = run.products.filter(is_active=True).first()
        discount = determine_courseware_flexible_price_discount(
            ecommerce_product, request.user
        )
        finaid_price = (
            ecommerce_product.price,
            discount.discount_product(ecommerce_product),
        )
        product = ecommerce_product
    else:
        finaid_price = None
        product = None
    relevant_runs = list(CourseRun.objects.values("courseware_id", "start_date"))
    course_page = CoursePageFactory.create(**course_page_kwargs)
    if enrolled:
        CourseRunEnrollmentFactory.create(user=staff_user, run=run)

    context = course_page.get_context(request=request)
    assert context == {
        "self": course_page,
        "page": course_page,
        "request": request,
        "run": run,
        "course_runs": relevant_runs,
        "is_enrolled": exp_is_enrolled,
        "sign_in_url": f"/signin/?next={quote_plus(course_page.get_url())}"
        if exp_sign_in_url
        else None,
        "start_date": getattr(run, "start_date", None),
        "can_access_edx_course": is_authenticated and has_relevant_run,
        "finaid_price": finaid_price,
        "product": product,
    }

    context = course_page.get_context(request=request)

    if has_finaid:
        assert context["finaid_price"] == (
            ecommerce_product.price,
            discount.discount_product(ecommerce_product),
        )
    else:
        assert context["finaid_price"] is None


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
    flex_form = FlexiblePricingFormFactory(selected_course=course_page.course)

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
                courseware_object=course_page.course.program,
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
        FlexiblePriceStatus.CREATED,
        FlexiblePriceStatus.APPROVED,
        FlexiblePriceStatus.DENIED,
        FlexiblePriceStatus.RESET,
    ],
)
def test_flex_pricing_form_state_display(mocker, submission_status):
    """
    Tests the display when the user goes to submit a request again - they should
    get one of three status update pages instead of the form.
    """

    course_page = CoursePageFactory.create(course__readable_id=FAKE_READABLE_ID)
    flex_form = FlexiblePricingFormFactory(selected_course=course_page.course)

    request_user = UserFactory.create()
    submission = FlexiblePricingRequestSubmission.objects.create(
        form_data=json.dumps([]), page=flex_form, user=request_user
    )
    flexprice = FlexiblePrice.objects.create(
        user=request_user,
        cms_submission=submission,
        status=submission_status,
        courseware_object=course_page.course.program,
    )

    response = generate_flexible_pricing_response(request_user, flex_form)

    if submission_status == FlexiblePriceStatus.CREATED:
        assert "Application Processing" in response.rendered_content
    elif submission_status == FlexiblePriceStatus.APPROVED:
        assert "Application Approved" in response.rendered_content
    elif submission_status == FlexiblePriceStatus.DENIED:
        assert "Application Denied" in response.rendered_content
    elif submission_status == FlexiblePriceStatus.RESET:
        assert (
            "csrfmiddlewaretoken" in response.rendered_content
        ), response.rendered_content


@pytest.mark.parametrize("course_or_program", [True, False])
def test_flex_pricing_parent_resources(course_or_program):
    """
    Tests the get_parent_product and get_parent_product_page methods in the
    FlexiblePricingRequestForm to make sure the right things are returned based
    on whether the form is under a CoursePage or a ProgramPage.

    Args:
    - course_or_program: boolean, True to test with a CoursePage, False for ProgramPage.
    """

    if course_or_program:
        parent_page = CoursePageFactory.create()
    else:
        parent_page = ProgramPageFactory.create()

    flex_form = FlexiblePricingFormFactory(parent=parent_page)

    assert (
        isinstance(flex_form.get_parent_product_page(), CoursePage)
        if course_or_program
        else isinstance(flex_form.get_parent_product_page(), ProgramPage)
    )


def test_flex_pricing_form_courseware_object():
    """
    Tests to make sure the correct courseware objects are returned when hitting
    the get_parent_courseware method.
    """

    course_page = CoursePageFactory.create(course__readable_id=FAKE_READABLE_ID)
    flex_form = FlexiblePricingFormFactory()

    program = ProgramFactory.create()
    secondary_course = CourseFactory.create(program=program)

    # no set courseware object, so get it from the parent page

    assert flex_form.get_parent_courseware() == course_page.course.program
    assert flex_form.selected_course is None
    assert flex_form.selected_program is None

    # setting a specific course (but not a program) - should return the program

    flex_form.selected_course = secondary_course
    flex_form.save()
    flex_form.refresh_from_db()

    assert flex_form.get_parent_courseware() == program
    assert flex_form.selected_course == secondary_course
    assert flex_form.selected_program is None

    # setting a specific program - should override everything

    flex_form.selected_program = program
    flex_form.save()
    flex_form.refresh_from_db()

    assert flex_form.get_parent_courseware() == program
    assert flex_form.selected_course == secondary_course
    assert flex_form.selected_program == program


@pytest.mark.parametrize("test_course_first", [True, False])
def test_flex_pricing_single_submission(mocker, test_course_first):
    """
    Tests multiple submissions for the same course/program.

    If the FlexiblePricingRequestForm is associated with a course, it should
    check for a submission for that course or the program the course belongs to.
    If it's associated with a program, it should check for submissions in the
    program. A submission for a course in the program should exist for the program.
    """
    program = ProgramFactory.create()
    course = CourseFactory.create(program=program)

    course_page = CoursePageFactory.create(course__readable_id=FAKE_READABLE_ID)

    if test_course_first:
        first_sub_form = FlexiblePricingFormFactory(
            parent=course_page, selected_course=course
        )
        second_sub_form = FlexiblePricingFormFactory(
            parent=course_page, selected_program=program
        )
    else:
        second_sub_form = FlexiblePricingFormFactory(
            parent=course_page, selected_course=course
        )
        first_sub_form = FlexiblePricingFormFactory(
            parent=course_page, selected_program=program
        )

    request_user = UserFactory.create()
    submission = FlexiblePricingRequestSubmission.objects.create(
        form_data=json.dumps([]), page=first_sub_form, user=request_user
    )

    flexprice = FlexiblePrice.objects.create(
        user=request_user,
        cms_submission=submission,
        courseware_object=program,
        status=FlexiblePriceStatus.CREATED,
    )

    # test to make sure we get back a status message from the first form

    response = generate_flexible_pricing_response(request_user, first_sub_form)

    assert "Application Processing" in response.rendered_content

    # then test to make sure we get a status message back from the second form too

    response = generate_flexible_pricing_response(request_user, second_sub_form)

    # should not get a form here - should get Application Processing

    assert "Application Processing" in response.rendered_content


def test_flex_pricing_form_state_display_no_discount_tier(mocker):
    """
    Tests the status display when the user is assigned to the no-discount tier.
    """

    course_page = CoursePageFactory.create(course__readable_id=FAKE_READABLE_ID)
    flex_form = FlexiblePricingFormFactory(
        selected_course=course_page.course,
        application_approved_no_discount_text="No Discount Text",
        application_approved_text="Application Approved",
    )
    tier = FlexiblePriceTierFactory(
        courseware_object=course_page.course.program, discount__amount=0
    )
    other_tier = FlexiblePriceTierFactory(
        courseware_object=course_page.course.program,
        discount__amount=50,
        discount__discount_type=DISCOUNT_TYPE_FIXED_PRICE,
    )

    request_user = UserFactory.create()
    submission = FlexiblePricingRequestSubmission.objects.create(
        form_data=json.dumps([]), page=flex_form, user=request_user
    )
    flexprice = FlexiblePrice.objects.create(
        user=request_user,
        cms_submission=submission,
        status=FlexiblePriceStatus.APPROVED,
        courseware_object=course_page.course.program,
        tier=tier,
    )

    response = generate_flexible_pricing_response(request_user, flex_form)

    assert "No Discount Text" in response.rendered_content

    flexprice.tier = other_tier
    flexprice.save()
    flexprice.refresh_from_db()

    response = generate_flexible_pricing_response(request_user, flex_form)

    assert "Approved" in response.rendered_content
