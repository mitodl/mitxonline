"""Tests for CMS app API functionality"""
import pytest
from django.contrib.contenttypes.models import ContentType
from courses.models import ProgramRequirement, ProgramRequirementNodeType
from wagtail.models import Page
from wagtail_factories import PageFactory
from django.core.exceptions import ValidationError


from cms.api import (
    ensure_home_page_and_site,
    get_wagtail_img_src,
    ensure_resource_pages,
    ensure_product_index,
    get_home_page,
    RESOURCE_PAGE_TITLES,
    ensure_program_product_index,
    create_default_courseware_page,
)
from cms.exceptions import WagtailSpecificPageError
from cms.factories import HomePageFactory, CoursePageFactory, ProgramPageFactory
from cms.models import (
    HomePage,
    ResourcePage,
    CourseIndexPage,
    HomeProductLink,
    ProgramIndexPage,
    CoursePage,
    ProgramPage,
)

from courses.factories import CourseFactory, ProgramFactory, ProgramRequirementFactory


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
def test_home_page_featured_products(mocker):
    """test home page is loading featured product"""
    home_page = HomePageFactory.create()
    patched_get_home_page = mocker.patch(
        "cms.api.get_home_page", return_value=home_page
    )
    course_page = CoursePageFactory.create(parent=home_page)
    # make sure featured products are listing
    HomeProductLink.objects.create(page=home_page, course_product_page=course_page)
    featured_products = home_page.products
    assert len(featured_products) == 1
    run = course_page.product.first_unexpired_run
    assert featured_products == [
        {
            "title": course_page.title,
            "description": course_page.description,
            "feature_image": course_page.feature_image,
            "start_date": run.start_date if run is not None else None,
            "url_path": course_page.get_url(),
            "is_program": False,
            "program_type": None,
        }
    ]


@pytest.mark.django_db
def test_home_page_featured_products_sorting(mocker):
    """tests that featured products are sorted in ascending order"""
    home_page = HomePageFactory.create()
    patched_get_home_page = mocker.patch(
        "cms.api.get_home_page", return_value=home_page
    )
    course_pages = CoursePageFactory.create_batch(2, parent=home_page)
    page_data = []
    for course_page in course_pages:
        HomeProductLink.objects.create(page=home_page, course_product_page=course_page)
        run = course_page.product.first_unexpired_run
        page_data.append(
            {
                "title": course_page.title,
                "description": course_page.description,
                "feature_image": course_page.feature_image,
                "start_date": run.start_date if run is not None else None,
                "url_path": course_page.get_url(),
                "is_program": False,
                "program_type": None,
            }
        )

    page_data = sorted(
        page_data,
        key=lambda item: (item["start_date"] is None, item["start_date"]),
    )
    featured_products = home_page.products
    assert len(featured_products) == 2
    assert featured_products == page_data


@pytest.mark.django_db
def test_home_page_featured_products_published_only():
    """Tests that featured products contain only published products/pages in the HomePage"""
    home_page = HomePageFactory.create()
    course_pages = CoursePageFactory.create_batch(2, parent=home_page)
    program_pages = ProgramPageFactory.create_batch(2, parent=home_page)
    unpublished_course_page = CoursePageFactory.create(parent=home_page, live=False)
    unpublished_program_page = ProgramPageFactory.create(parent=home_page, live=False)

    for course_page in course_pages + [unpublished_course_page]:
        HomeProductLink.objects.create(page=home_page, course_product_page=course_page)

    for program_page in program_pages + [unpublished_program_page]:
        HomeProductLink.objects.create(page=home_page, course_product_page=program_page)

    featured_products = home_page.products
    assert len(featured_products) == 4
    assert unpublished_course_page not in featured_products
    assert unpublished_program_page not in featured_products


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
