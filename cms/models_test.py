"""Tests for Wagtail models"""

import json
from datetime import timedelta
from urllib.parse import quote_plus

import factory
import pytest
from django.contrib.auth.models import AnonymousUser, Group
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.cache import caches
from django.test.client import RequestFactory
from django.urls import resolve
from mitol.common.factories import UserFactory
from mitol.common.utils.datetime import now_in_utc

from cms.api import create_featured_items
from cms.constants import CMS_EDITORS_GROUP_NAME
from cms.factories import (
    CertificatePageFactory,
    CoursePageFactory,
    FlexiblePricingFormFactory,
    HomePageFactory,
    InstructorPageFactory,
    ProgramPageFactory,
    ResourcePageFactory,
)
from cms.models import (
    CertificatePage,
    CoursePage,
    FlexiblePricingRequestSubmission,
    InstructorPageLink,
    ProgramPage,
    SignatoryPage,
)
from courses.factories import (
    CourseFactory,
    CourseRunEnrollmentFactory,
    CourseRunFactory,
    ProgramFactory,
    program_with_empty_requirements,  # noqa: F401
)
from courses.models import Course, CourseRun
from ecommerce.constants import DISCOUNT_TYPE_FIXED_PRICE
from ecommerce.factories import ProductFactory
from flexiblepricing.api import determine_courseware_flexible_price_discount
from flexiblepricing.constants import FlexiblePriceStatus
from flexiblepricing.factories import FlexiblePriceFactory, FlexiblePriceTierFactory
from flexiblepricing.models import FlexiblePrice

pytestmark = [pytest.mark.django_db]

FAKE_READABLE_ID = "some:readable-id"


def test_resource_page_site_name(settings, mocker):
    """
    ResourcePage should include site_name in its context
    """
    settings.SITE_NAME = "a site's name"
    page = ResourcePageFactory.create()
    rf = RequestFactory()
    request = rf.get("/")
    mocker.patch("cms.models.get_base_context")
    assert page.get_context(request)["site_name"] == settings.SITE_NAME


def test_custom_detail_page_urls(fully_configured_wagtail):
    """Verify that course detail pages return our custom URL path"""
    course_pages = CoursePageFactory.create_batch(
        2, course__readable_id=factory.Iterator([FAKE_READABLE_ID, "non-matching-id"])
    )
    assert course_pages[0].get_url() == f"/courses/{FAKE_READABLE_ID}/"


def test_custom_detail_page_urls_handled(fully_configured_wagtail):
    """Verify that custom URL paths for our course pages are served by the standard Wagtail view"""
    CoursePageFactory.create(course__readable_id=FAKE_READABLE_ID)
    resolver_match = resolve(f"/courses/{FAKE_READABLE_ID}/")
    assert resolver_match.func.__module__ == "wagtail.views"  # pylint: disable=protected-access
    assert resolver_match.func.__name__ == "serve"  # pylint: disable=protected-access


@pytest.mark.parametrize(
    "is_authenticated,has_relevant_run,enrolled,exp_sign_in_url,exp_is_enrolled,has_finaid,has_instructor",  # noqa: PT006
    [
        [True, True, True, False, True, True, True],  # noqa: PT007
        [True, True, True, False, True, False, False],  # noqa: PT007
        [  # noqa: PT007
            False,
            False,
            False,
            True,
            False,
            False,
            True,
        ],
        [False, True, True, True, False, False, False],  # noqa: PT007
    ],
)
def test_course_page_context(  # noqa: PLR0913
    staff_user,
    fully_configured_wagtail,
    is_authenticated,
    has_relevant_run,
    enrolled,
    exp_sign_in_url,
    exp_is_enrolled,
    has_finaid,
    has_instructor,
):
    """CoursePage.get_context should return expected values"""
    rf = RequestFactory()
    request = rf.get("/")
    request.user = staff_user if is_authenticated else AnonymousUser()
    if has_relevant_run:
        run = CourseRunFactory.create(
            course__page=None, course__readable_id=FAKE_READABLE_ID, in_future=True
        )
        course_page_kwargs = dict(course=run.course)  # noqa: C408
    else:
        run = None
        course_page_kwargs = dict(course__readable_id=FAKE_READABLE_ID)  # noqa: C408
    if has_finaid and is_authenticated and has_relevant_run:
        sub = FlexiblePriceFactory(  # noqa: F841
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
    relevant_runs = list(CourseRun.objects.all())
    course_page = CoursePageFactory.create(**course_page_kwargs)
    if enrolled:
        CourseRunEnrollmentFactory.create(user=staff_user, run=run)

    if has_instructor:
        instructor_page = InstructorPageFactory.create()
        InstructorPageLink.objects.create(
            page=course_page, linked_instructor_page=instructor_page
        )
        course_page.refresh_from_db()

    context = course_page.get_context(request=request)
    assert context == {
        "self": course_page,
        "page": course_page,
        "request": request,
        "run": run,
        "course_runs": relevant_runs,
        "sign_in_url": f"/signin/?next={quote_plus(course_page.get_url())}"
        if exp_sign_in_url
        else None,
        "start_date": getattr(run, "start_date", None),
        "can_access_edx_course": is_authenticated and has_relevant_run,
        "finaid_price": finaid_price,
        "product": product,
        "hijack_logout_redirect_url": "/admin/users/user",
        "instructors": []
        if not has_instructor
        else [
            member.linked_instructor_page
            for member in course_page.linked_instructors.order_by("order").all()
        ],
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
    "is_authed,is_editor,has_relevant_run,is_in_progress,exp_can_access",  # noqa: PT006
    [
        [True, True, True, True, True],  # noqa: PT007
        [False, False, True, True, False],  # noqa: PT007
        [True, True, True, False, True],  # noqa: PT007
        [True, True, False, True, False],  # noqa: PT007
        [True, False, True, False, False],  # noqa: PT007
    ],
)
def test_course_page_context_edx_access(  # noqa: PLR0913
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
            **(dict(in_progress=True) if is_in_progress else dict(in_future=True)),  # noqa: C408
        )
    )
    patched_get_relevant_run_qset = mocker.patch(
        "cms.models.get_relevant_course_run_qset", return_value=[run if run else None]
    )
    if not is_authed:  # noqa: SIM108
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
    patched_get_relevant_run_qset.assert_called_once_with(course=course_page.course)


def generate_flexible_pricing_response(mocker, request_user, flexible_pricing_form):
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
    get_response = mocker.MagicMock()
    middleware = SessionMiddleware(get_response)
    middleware.process_request(request)
    request.session.save()

    response = flexible_pricing_form.serve(request)
    response.render()

    assert response.is_rendered

    return response


@pytest.mark.parametrize(
    "is_authed,has_submission",  # noqa: PT006
    [[False, False], [True, False], [True, True]],  # noqa: PT007
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
            flexprice = FlexiblePrice.objects.create(  # noqa: F841
                user=request_user,
                cms_submission=submission,
                courseware_object=flex_form.selected_course,
            )

    response = generate_flexible_pricing_response(mocker, request_user, flex_form)

    # simple string checking for the rendered content
    # should match what's in the factory

    if not is_authed:
        assert "Not Logged In" in response.rendered_content
    elif has_submission:
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
    flexprice = FlexiblePrice.objects.create(  # noqa: F841
        user=request_user,
        cms_submission=submission,
        status=submission_status,
        courseware_object=course_page.course,
    )

    response = generate_flexible_pricing_response(mocker, request_user, flex_form)

    if submission_status == FlexiblePriceStatus.CREATED:
        assert "Application Processing" in response.rendered_content
    elif submission_status == FlexiblePriceStatus.APPROVED:
        assert "Application Approved" in response.rendered_content
    elif submission_status == FlexiblePriceStatus.DENIED:
        assert "Application Denied" in response.rendered_content
    elif submission_status == FlexiblePriceStatus.RESET:
        assert "csrfmiddlewaretoken" in response.rendered_content, (
            response.rendered_content
        )


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


def test_flex_pricing_form_courseware_object(program_with_empty_requirements):  # noqa: F811
    """
    Tests to make sure the correct courseware objects are returned when hitting
    the get_parent_courseware method.
    """

    first_course = CourseFactory.create(readable_id=FAKE_READABLE_ID, page=None)
    course_page = CoursePageFactory.create(course=first_course)  # noqa: F841
    flex_form = FlexiblePricingFormFactory()

    program = program_with_empty_requirements
    secondary_course = CourseFactory.create()
    program.add_requirement(secondary_course)

    # no set courseware object, so get it from the parent page

    assert flex_form.get_parent_courseware() == first_course
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

    # adding a second program - should still return the first program

    second_program = ProgramFactory.create()
    second_program.add_requirement(secondary_course)

    assert flex_form.get_parent_courseware() == program
    assert flex_form.selected_course == secondary_course
    assert flex_form.selected_program == program


@pytest.mark.parametrize("test_scenario", ["course", "two_programs", "one_program"])
def test_flex_pricing_single_submission(
    mocker,
    test_scenario,
    program_with_empty_requirements,  # noqa: F811
):
    """
    Tests multiple submissions for the same course/program.

    If the FlexiblePricingRequestForm is associated with a course, it should
    check for a submission for that course or the program the course belongs to.
    If it's associated with a program, it should check for submissions in the
    program. A submission for a course in the program should exist for the program.
    If it's associated with a program that has related programs, it should check
    for submissions in the related programs too.
    """
    program = program_with_empty_requirements
    course = CourseFactory.create()
    program.add_requirement(course)

    course_page = CoursePageFactory.create(course__readable_id=FAKE_READABLE_ID)

    if test_scenario == "course":
        first_sub_form = FlexiblePricingFormFactory(
            parent=course_page, selected_course=course
        )
        second_sub_form = FlexiblePricingFormFactory(
            parent=course_page, selected_program=program
        )
    elif test_scenario == "two_programs":
        second_program = ProgramFactory.create()
        second_program.add_requirement(course)
        second_program.add_related_program(program)

        first_sub_form = FlexiblePricingFormFactory(
            parent=course_page, selected_program=program
        )
        second_sub_form = FlexiblePricingFormFactory(
            parent=course_page, selected_program=second_program
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

    flexprice = FlexiblePrice.objects.create(  # noqa: F841
        user=request_user,
        cms_submission=submission,
        courseware_object=program,
        status=FlexiblePriceStatus.CREATED,
    )

    # test to make sure we get back a status message from the first form

    response = generate_flexible_pricing_response(mocker, request_user, first_sub_form)

    assert "Application Processing" in response.rendered_content

    # then test to make sure we get a status message back from the second form too

    response = generate_flexible_pricing_response(mocker, request_user, second_sub_form)

    # should not get a form here - should get Application Processing

    assert "Application Processing" in response.rendered_content


def test_flex_pricing_form_state_display_no_discount_tier(
    mocker,
    program_with_empty_requirements,  # noqa: F811
):
    """
    Tests the status display when the user is assigned to the no-discount tier.
    """

    program = program_with_empty_requirements
    course_page = CoursePageFactory.create(course__readable_id=FAKE_READABLE_ID)
    program.add_requirement(course_page.course)
    course_page.refresh_from_db()
    program.refresh_from_db()

    flex_form = FlexiblePricingFormFactory(
        selected_course=course_page.course,
        application_approved_no_discount_text="No Discount Text",
        application_approved_text="Application Approved",
    )
    tier = FlexiblePriceTierFactory(
        courseware_object=course_page.course.programs[0], discount__amount=0
    )
    other_tier = FlexiblePriceTierFactory(
        courseware_object=course_page.course.programs[0],
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
        courseware_object=course_page.course.programs[0],
        tier=tier,
    )

    response = generate_flexible_pricing_response(mocker, request_user, flex_form)

    assert "No Discount Text" in response.rendered_content

    flexprice.tier = other_tier
    flexprice.save()
    flexprice.refresh_from_db()

    response = generate_flexible_pricing_response(mocker, request_user, flex_form)

    assert "Approved" in response.rendered_content


def test_certificate_for_course_page():
    """
    The Certificate property should return expected values if associated with a CertificatePage
    """
    course_page = CoursePageFactory.create(certificate_page=None)
    assert CertificatePage.can_create_at(course_page)
    assert not SignatoryPage.can_create_at(course_page)

    certificate_page = CertificatePageFactory.create(
        parent=course_page,
        product_name="product_name",
        CEUs="1.8",
        signatories__0__signatory__page__name="Name",
        signatories__0__signatory__page__title_1="Title_1",
        signatories__0__signatory__page__title_2="Title_2",
        signatories__0__signatory__page__organization="Organization",
        signatories__0__signatory__page__signature_image__title="Image",
    )
    assert certificate_page.get_parent() == course_page
    assert certificate_page.CEUs == "1.8"
    assert certificate_page.product_name == "product_name"
    for signatory in certificate_page.signatories:  # pylint: disable=not-an-iterable
        assert signatory.value.name == "Name"
        assert signatory.value.title_1 == "Title_1"
        assert signatory.value.title_2 == "Title_2"
        assert signatory.value.organization == "Organization"
        assert signatory.value.signature_image.title == "Image"


def test_certificate_for_program_page():
    """
    The Certificate property should return expected values if associated with a CertificatePage
    """
    program_page = ProgramPageFactory.create(certificate_page=None)
    assert CertificatePage.can_create_at(program_page)
    assert not SignatoryPage.can_create_at(program_page)

    certificate_page = CertificatePageFactory.create(
        parent=program_page,
        product_name="product_name",
        CEUs="2.8",
        signatories__0__signatory__page__name="Name",
        signatories__0__signatory__page__title_1="Title_1",
        signatories__0__signatory__page__title_2="Title_2",
        signatories__0__signatory__page__organization="Organization",
        signatories__0__signatory__page__signature_image__title="Image",
    )

    assert certificate_page.get_parent() == program_page
    assert certificate_page.CEUs == "2.8"
    assert certificate_page.product_name == "product_name"
    for signatory in certificate_page.signatories:  # pylint: disable=not-an-iterable
        assert signatory.value.name == "Name"
        assert signatory.value.title_1 == "Title_1"
        assert signatory.value.title_2 == "Title_2"
        assert signatory.value.organization == "Organization"
        assert signatory.value.signature_image.title == "Image"


@pytest.mark.parametrize("test_course", [True, False])
def test_courseware_title_synced_with_product_page_title(test_course):
    """Tests that Courseware title is synced with the Course Page title from CMS"""
    product_page = CoursePageFactory() if test_course else ProgramPageFactory()
    updated_title = "Updated Courseware Page Title"
    product_page.title = updated_title
    product_page.save()

    courseware = product_page.course if test_course else product_page.program

    assert courseware.title == updated_title


@pytest.mark.parametrize("flex_form_for_course", [True, False])
def test_flexible_pricing_request_form_context(flex_form_for_course):
    """
    Tests the flexible pricing request form context contains required information.
    The context["product"] will contain different values based on whether the
    Flexible Pricing request is for a Course or Program.
    """
    rf = RequestFactory()
    request = rf.get("/")
    user = UserFactory.create()
    request.user = user
    course_page = CoursePageFactory()
    run = CourseRunFactory.create(course=course_page.course)

    if flex_form_for_course:
        parent_page = CoursePageFactory.create()
        flex_form = FlexiblePricingFormFactory(
            selected_course=course_page.course, parent=parent_page
        )
    else:
        parent_page = ProgramPageFactory.create()
        flex_form = FlexiblePricingFormFactory(parent=parent_page)
    product = ProductFactory.create(purchasable_object=run)

    context = flex_form.get_context(request=request)
    if isinstance(product, Course):
        assert context["product"].id == product.id
    else:
        assert context["product"] is None
    assert context["product_page"] == course_page.url


def test_homepage__featured_products(settings, mocker):
    now = now_in_utc()
    future_date = now + timedelta(days=1)
    past_date = now - timedelta(days=1)
    further_future_date = future_date + timedelta(days=1)
    further_past_date = past_date - timedelta(days=1)
    furthest_future_date = further_future_date + timedelta(days=1)
    redis_cache = caches["redis"]
    # Ensure the key is empty since pytest doesn't clear the cache between tests
    featured_courses = redis_cache.get("CMS_homepage_featured_courses")
    if featured_courses is not None:
        redis_cache.delete("CMS_homepage_featured_courses")
    assert redis_cache.get("CMS_homepage_featured_courses") is None

    enrollable_future_course = CourseFactory.create(page=None, live=True)
    enrollable_future_course_page = CoursePageFactory.create(
        course=enrollable_future_course, live=True
    )
    enrollable_future_courserun = CourseRunFactory.create(
        course=enrollable_future_course,
        live=True,
        start_date=future_date,
        enrollment_start=further_past_date,
        enrollment_end=further_future_date,
        end_date=furthest_future_date,
    )
    create_featured_items()
    assert len(redis_cache.get("CMS_homepage_featured_courses")) == 1
    hf = HomePageFactory.create()
    assert hf.get_cached_featured_products == [
        {
            "title": enrollable_future_course_page.title,
            "description": enrollable_future_course_page.description,
            "feature_image": enrollable_future_course_page.feature_image,
            "start_date": enrollable_future_courserun.start_date,
            "url_path": enrollable_future_course_page.get_url(),
            "is_program": enrollable_future_course_page.is_program_page,
            "is_self_paced": False,
            "program_type": None,
        }
    ]
    # Remove the previous course from the potential courses to be featured, this will also test a course as unenrollable
    enrollable_future_course.live = False
    enrollable_future_course.save()

    enrollable_future_course_with_no_enrollment_end = CourseFactory.create(
        page=None, live=True
    )
    enrollable_future_course_with_no_enrollment_end_page = CoursePageFactory.create(
        course=enrollable_future_course_with_no_enrollment_end, live=True
    )
    enrollable_future_courserun_with_no_enrollment_end = CourseRunFactory.create(
        course=enrollable_future_course_with_no_enrollment_end,
        live=True,
        start_date=future_date,
        enrollment_start=further_past_date,
        enrollment_end=None,
        end_date=furthest_future_date,
    )
    create_featured_items()
    assert len(redis_cache.get("CMS_homepage_featured_courses")) == 1
    hf = HomePageFactory.create()
    assert hf.get_cached_featured_products == [
        {
            "title": enrollable_future_course_with_no_enrollment_end_page.title,
            "description": enrollable_future_course_with_no_enrollment_end_page.description,
            "feature_image": enrollable_future_course_with_no_enrollment_end_page.feature_image,
            "start_date": enrollable_future_courserun_with_no_enrollment_end.start_date,
            "url_path": enrollable_future_course_with_no_enrollment_end_page.get_url(),
            "is_program": enrollable_future_course_with_no_enrollment_end_page.is_program_page,
            "is_self_paced": False,
            "program_type": None,
        }
    ]
