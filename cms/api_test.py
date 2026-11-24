"""Tests for CMS app API functionality"""

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from wagtail.models import Page
from wagtail_factories import ImageFactory, PageFactory

from cms.api import (
    RESOURCE_PAGE_TITLES,
    _FinancialAssistanceForms,
    create_default_courseware_page,
    ensure_home_page_and_site,
    ensure_product_index,
    ensure_program_product_index,
    ensure_resource_pages,
    get_home_page,
    get_wagtail_img_src,
    resolve_financial_assistance_form_urls,
)
from cms.exceptions import WagtailSpecificPageError
from cms.factories import (
    CoursePageFactory,
    FlexiblePricingFormFactory,
    HomePageFactory,
    ProgramPageFactory,
)
from cms.models import (
    CourseIndexPage,
    CoursePage,
    HomePage,
    ProgramIndexPage,
    ProgramPage,
    ResourcePage,
)
from courses.factories import CourseFactory, ProgramFactory
from courses.models import Program, default_program_queryset

# resolve_financial_assistance_form_urls does a fixed number of queries:
# course pages, programs, related programs, program pages, live forms. This is
# an upper bound; the property that matters is that it does not scale with the
# number of courses asked for.
FINANCIAL_ASSISTANCE_QUERY_COUNT = 6


@pytest.mark.django_db
def test_get_home_page():
    """
    get_home_page should fetch a Page object for the home page or raise exceptions if certain conditions are met
    """
    with pytest.raises(Page.DoesNotExist):
        get_home_page()
    assert get_home_page(raise_if_missing=False) is None
    # Orphaned home page (no HomePage record associated with the Page record
    orphaned_home_page = PageFactory.create(
        content_type=ContentType.objects.get_for_model(HomePage)
    )
    with pytest.raises(WagtailSpecificPageError):
        get_home_page(check_specific=True)
    assert get_home_page() == orphaned_home_page


@pytest.mark.django_db
def test_get_home_page_specific():
    """
    get_home_page should fetch a Page object successfully if check_specific=True and there is a HomePage record
    associated with that Page
    """
    home_page = HomePageFactory.create()
    returned_home_page = get_home_page(check_specific=True)
    assert home_page.page_ptr == returned_home_page


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
    # Make sure the function is idempotent
    ensure_home_page_and_site()
    assert home_page_qset.count() == 1


@pytest.mark.django_db
def test_get_wagtail_img_src(settings):
    """get_wagtail_img_src should return the correct image URL"""
    settings.MEDIA_URL = "/mediatest/"
    settings.SITE_BASE_URL = "http://mitxonline.test"
    img_filename = "path/to/my-image.jpg"
    img_hash = "abc123"
    image = ImageFactory.build(file__filename=img_filename, file_hash=img_hash)
    img_src = get_wagtail_img_src(image)
    assert img_src == f"http://mitxonline.test/mediatest/{img_filename}?v={img_hash}"


@pytest.mark.django_db
def test_ensure_resource_pages(mocker):
    """
    ensure_resource_pages should create resource pages if they don't already exist
    """
    patched_get_home_page = mocker.patch(
        "cms.api.get_home_page", return_value=HomePageFactory.create()
    )
    expected_resource_pages = len(RESOURCE_PAGE_TITLES)
    resource_page_qset = Page.objects.filter(
        content_type=ContentType.objects.get_for_model(ResourcePage)
    )
    assert resource_page_qset.exists() is False
    assert resource_page_qset.count() == 0
    ensure_resource_pages()
    patched_get_home_page.assert_called_once()
    assert resource_page_qset.exists() is True
    assert resource_page_qset.count() == expected_resource_pages
    assert sorted(
        [resource_page.title for resource_page in resource_page_qset]
    ) == sorted(RESOURCE_PAGE_TITLES)
    # Make sure the function is idempotent
    ensure_resource_pages()
    assert resource_page_qset.count() == expected_resource_pages


@pytest.mark.django_db
def test_ensure_product_index(mocker):
    """
    ensure_product_index should make sure that a course index page exists and that all course detail pages are nested
    under it
    """
    home_page = HomePageFactory.create()
    patched_get_home_page = mocker.patch(
        "cms.api.get_home_page", return_value=home_page
    )
    existing_course_page = CoursePageFactory.create(parent=home_page)
    course_index_qset = Page.objects.filter(
        content_type=ContentType.objects.get_for_model(CourseIndexPage)
    )
    assert existing_course_page.get_parent() == home_page
    assert course_index_qset.exists() is False
    ensure_product_index()
    patched_get_home_page.assert_called_once()
    course_index_page = course_index_qset.first()
    assert course_index_page is not None
    course_index_children_qset = course_index_page.get_children()
    assert list(course_index_children_qset.all()) == [existing_course_page.page_ptr]
    # Make sure the function is idempotent
    ensure_product_index()
    assert list(course_index_children_qset.all()) == [existing_course_page.page_ptr]


@pytest.mark.django_db
def test_ensure_program_product_index(mocker):
    """
    Same as test_ensure_product_index, but operates on ProgramPages instead.
    """
    home_page = HomePageFactory.create()
    patched_get_home_page = mocker.patch(
        "cms.api.get_home_page", return_value=home_page
    )
    existing_program_page = ProgramPageFactory.create(parent=home_page)
    program_index_qset = Page.objects.filter(
        content_type=ContentType.objects.get_for_model(ProgramIndexPage)
    )
    assert existing_program_page.get_parent() == home_page
    assert program_index_qset.exists() is False
    ensure_program_product_index()
    patched_get_home_page.assert_called_once()
    program_index_page = program_index_qset.first()
    assert program_index_page is not None
    program_index_children_qset = program_index_page.get_children()
    assert list(program_index_children_qset.all()) == [existing_program_page.page_ptr]
    # Make sure the function is idempotent
    ensure_program_product_index()
    assert list(program_index_children_qset.all()) == [existing_program_page.page_ptr]


@pytest.mark.django_db
def test_create_courseware_page():
    ensure_home_page_and_site()
    ensure_product_index()
    ensure_program_product_index()

    course = CourseFactory.create(page=None)
    program = ProgramFactory.create(page=None)
    program.add_requirement(course)

    resulting_page = create_default_courseware_page(course)

    assert isinstance(resulting_page, CoursePage)
    assert resulting_page.title == course.title

    with pytest.raises(ValidationError):
        resulting_page = create_default_courseware_page(course)

    resulting_page = create_default_courseware_page(course.programs[0])

    assert isinstance(resulting_page, ProgramPage)
    assert resulting_page.title == course.programs[0].title

    with pytest.raises(ValidationError):
        resulting_page = create_default_courseware_page(course.programs[0])


def _url_for(course, program_queryset=None):
    """The resolved financial assistance form URL for one course."""
    return resolve_financial_assistance_form_urls(
        [course.id], program_queryset=program_queryset
    )[course.id]


@pytest.mark.django_db
def test_financial_assistance_url_child_form():
    """
    A form that is a child page of the course page.

    Exercises the treebeard path arithmetic standing in for Wagtail's
    ``get_children()``.
    """
    page = CoursePageFactory()
    page.product.program = None
    form = FlexiblePricingFormFactory(parent=page)

    assert _url_for(page.product).endswith(f"{form.slug}/")


@pytest.mark.django_db
def test_financial_assistance_url_course_specific_form():
    """A form linked to the course via ``selected_course``."""
    page = CoursePageFactory()
    form = FlexiblePricingFormFactory(
        parent=CoursePageFactory(), selected_course=page.product
    )

    assert _url_for(page.product).endswith(f"{form.slug}/")


@pytest.mark.django_db
def test_financial_assistance_url_own_program_form():
    """A form linked to one of the course's own programs."""
    program = ProgramFactory()
    page = CoursePageFactory()
    program.add_requirement(page.product)
    form = FlexiblePricingFormFactory(
        parent=CoursePageFactory(), selected_program=program
    )

    assert _url_for(page.product).endswith(f"{form.slug}/")


@pytest.mark.django_db
def test_financial_assistance_url_related_program_form():
    """A form linked to a program *related* to the course's program."""
    program = ProgramFactory()
    related = ProgramFactory()
    program.add_related_program(related)
    page = CoursePageFactory()
    program.add_requirement(page.product)
    form = FlexiblePricingFormFactory(
        parent=CoursePageFactory(), selected_program=related
    )

    assert _url_for(page.product).endswith(f"{form.slug}/")


@pytest.mark.django_db
def test_financial_assistance_url_absent_when_no_form():
    """No form anywhere yields an empty string."""
    page = CoursePageFactory()
    page.product.program = None

    assert _url_for(page.product) == ""


@pytest.mark.django_db
def test_financial_assistance_url_skips_programs_outside_the_scope():
    """
    A program the caller filtered out cannot supply the URL.

    The regression this guards: the v2 course list scopes its ``programs``
    prefetch to live, non-b2b programs, and the URL is chosen by walking a
    course's programs - so the two have to be asked the same question. Before
    this was threaded through, a course in a ``live=False`` program served that
    program's form.
    """
    program = ProgramFactory(live=False)
    page = CoursePageFactory()
    program.add_requirement(page.product)
    FlexiblePricingFormFactory(parent=CoursePageFactory(), selected_program=program)

    live_only = Program.objects.filter(live=True)

    assert _url_for(page.product, program_queryset=live_only) == ""
    # Same data, no scope: the form is reachable, so the assertion above is
    # about the scope rather than about the form being missing.
    assert _url_for(page.product, program_queryset=Program.objects.all()) != ""


@pytest.mark.django_db
def test_financial_assistance_url_default_scope_excludes_b2b_programs():
    """
    With no scope named, b2b-only programs are out.

    ``default_program_queryset()`` is what both this resolver and the
    ``programs`` prefetch fall back to, so a b2b-only program must not supply a
    URL to a caller that never asked about b2b.
    """
    program = ProgramFactory(b2b_only=True)
    page = CoursePageFactory()
    program.add_requirement(page.product)
    FlexiblePricingFormFactory(parent=CoursePageFactory(), selected_program=program)

    assert _url_for(page.product) == ""
    assert _url_for(page.product, program_queryset=Program.objects.all()) != ""


@pytest.mark.django_db
def test_financial_assistance_url_scope_is_not_reentered_by_related_programs():
    """
    A scoped-out program does not sneak back in as somebody's related program.

    Related programs are deliberately unscoped - they are reached *through* a
    course's own programs, which are scoped - so this pins down that the
    scoping happens at the only place it can: the course's own programs.
    """
    scoped_out = ProgramFactory(live=False)
    related = ProgramFactory()
    scoped_out.add_related_program(related)
    page = CoursePageFactory()
    scoped_out.add_requirement(page.product)
    FlexiblePricingFormFactory(parent=CoursePageFactory(), selected_program=related)

    assert (
        _url_for(page.product, program_queryset=Program.objects.filter(live=True)) == ""
    )


@pytest.mark.django_db
def test_financial_assistance_forms_load_is_scoped_to_the_request():
    """
    The forms query must not grow with the number of live forms on the site.

    The query count tests below cannot catch this: fetching the whole form table
    is still exactly one query, so a regression back to that would leave every
    other test in this file passing. What matters here is how many rows come
    back, which is why this asserts on the loaded buckets rather than on timing
    or query count.

    A form is reachable from a course only via one of the three lookups
    ``url_for`` performs - tied to the course, tied to one of its programs, or a
    child of one of the pages in play. Forms hung off unrelated course pages
    satisfy none of them.
    """
    page = CoursePageFactory()
    FlexiblePricingFormFactory(parent=page)
    course_ids = [page.product.id]

    def loaded_form_pks():
        forms = _FinancialAssistanceForms(course_ids, default_program_queryset())
        return {
            form.pk
            for bucket in (
                forms.forms_by_parent_path,
                forms.forms_by_course_id,
                forms.forms_by_program_id,
            )
            for rows in bucket.values()
            for form in rows
        }

    before = loaded_form_pks()
    assert before, "the course's own form should load"

    for _ in range(5):
        FlexiblePricingFormFactory(parent=CoursePageFactory())

    assert loaded_form_pks() == before


@pytest.mark.django_db
def test_financial_assistance_url_query_count_is_flat(django_assert_max_num_queries):
    """
    The resolver's query count must not grow with the number of courses.

    That is the whole reason it exists: the cascade costs 4-8 queries per course
    when resolved one at a time. Asserting that two cardinalities cost the same
    tests that property directly, and unlike a fixed number it cannot be thrown
    off by which test happens to warm Wagtail's cached site-root paths.
    """

    def make_courses(count):
        courses = []
        for _ in range(count):
            page = CoursePageFactory()
            FlexiblePricingFormFactory(parent=page)
            # A program with a related program, so the whole cascade runs - a
            # course with no programs short-circuits two of the queries.
            program = ProgramFactory()
            program.add_related_program(ProgramFactory())
            program.add_requirement(page.product)
            courses.append(page.product)
        return [course.id for course in courses]

    one = make_courses(1)
    many = make_courses(10)

    # The first get_url() in the process fetches the site root paths and caches
    # them; warm that here so it lands in neither measurement.
    resolve_financial_assistance_form_urls(one)

    with CaptureQueriesContext(connection) as one_ctx:
        assert resolve_financial_assistance_form_urls(one)
    with django_assert_max_num_queries(FINANCIAL_ASSISTANCE_QUERY_COUNT) as many_ctx:
        urls = resolve_financial_assistance_form_urls(many)

    assert len(urls) == len(many)
    assert all(url for url in urls.values())
    assert len(many_ctx.captured_queries) == len(one_ctx.captured_queries)
