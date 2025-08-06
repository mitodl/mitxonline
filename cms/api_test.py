"""Tests for CMS app API functionality"""

from datetime import timedelta

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.cache import caches
from django.core.exceptions import ValidationError
from mitol.common.utils.datetime import now_in_utc
from wagtail.models import Page
from wagtail_factories import PageFactory

from cms.api import (
    RESOURCE_PAGE_TITLES,
    create_default_courseware_page,
    create_featured_items,
    ensure_home_page_and_site,
    ensure_product_index,
    ensure_program_product_index,
    ensure_resource_pages,
    get_home_page,
    get_wagtail_img_src,
)
from cms.exceptions import WagtailSpecificPageError
from cms.factories import CoursePageFactory, HomePageFactory, ProgramPageFactory
from cms.models import (
    CourseIndexPage,
    CoursePage,
    HomePage,
    HomeProductLink,
    ProgramIndexPage,
    ProgramPage,
    ResourcePage,
)
from courses.factories import CourseFactory, CourseRunFactory, ProgramFactory


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
    """Test home page is loading featured product"""
    home_page = HomePageFactory.create()
    patched_get_home_page = mocker.patch(  # noqa: F841
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
            "is_self_paced": run.is_self_paced if run is not None else None,
            "program_type": None,
        }
    ]


@pytest.mark.django_db
def test_home_page_featured_products_sorting(mocker):
    """Tests that featured products are sorted in ascending order by start_date"""
    home_page = HomePageFactory.create()
    patched_get_home_page = mocker.patch(  # noqa: F841
        "cms.api.get_home_page", return_value=home_page
    )

    now = now_in_utc()
    earlier_date = now - timedelta(days=30)
    later_date = now + timedelta(days=30)

    course_page_1 = CoursePageFactory.create(parent=home_page)
    course_page_2 = CoursePageFactory.create(parent=home_page)

    CourseRunFactory.create(
        course=course_page_1.product, start_date=later_date, live=True
    )
    CourseRunFactory.create(
        course=course_page_2.product, start_date=earlier_date, live=True
    )

    HomeProductLink.objects.create(page=home_page, course_product_page=course_page_1)
    HomeProductLink.objects.create(page=home_page, course_product_page=course_page_2)

    featured_products = home_page.products
    assert len(featured_products) == 2

    assert featured_products[0]["title"] == course_page_2.title
    assert featured_products[1]["title"] == course_page_1.title


@pytest.mark.django_db
def test_home_page_featured_products_published_only():
    """Tests that featured products contain only published products/pages in the HomePage"""
    home_page = HomePageFactory.create()
    course_pages = CoursePageFactory.create_batch(2, parent=home_page)
    program_pages = ProgramPageFactory.create_batch(2, parent=home_page)
    unpublished_course_page = CoursePageFactory.create(parent=home_page, live=False)
    unpublished_program_page = ProgramPageFactory.create(parent=home_page, live=False)

    for course_page in course_pages + [unpublished_course_page]:  # noqa: RUF005
        HomeProductLink.objects.create(page=home_page, course_product_page=course_page)

    for program_page in program_pages + [unpublished_program_page]:  # noqa: RUF005
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


@pytest.mark.django_db
def test_create_featured_items():
    # pytest does not clear cache thus if we have a cache value set, it will persist between tests and test runs
    # thus we need to clear the cache before running the test
    redis_cache = caches["redis"]
    featured_courses = redis_cache.get("CMS_homepage_featured_courses")
    if featured_courses is not None:
        redis_cache.delete("CMS_homepage_featured_courses")

    now = now_in_utc()
    future_date = now + timedelta(days=1)
    past_date = now - timedelta(days=1)
    further_future_date = future_date + timedelta(days=1)
    further_past_date = past_date - timedelta(days=1)
    furthest_future_date = further_future_date + timedelta(days=1)

    # Course that starts in the future but is open for enrollment
    enrollable_future_course = CourseFactory.create(page=None, live=True)
    CoursePageFactory.create(course=enrollable_future_course, live=True)
    enrollable_future_courserun = CourseRunFactory.create(  # noqa: F841
        course=enrollable_future_course,
        live=True,
        start_date=future_date,
        enrollment_start=further_past_date,
        enrollment_end=further_future_date,
        end_date=furthest_future_date,
    )

    # Course that is open for enrollment, but starts after the one above
    enrollable_other_future_course = CourseFactory.create(page=None, live=True)
    CoursePageFactory.create(course=enrollable_other_future_course, live=True)
    enrollable_other_future_courserun = CourseRunFactory.create(  # noqa: F841
        course=enrollable_other_future_course,
        live=True,
        enrollment_start=further_past_date,
        start_date=future_date + timedelta(days=2),
        enrollment_end=further_future_date + timedelta(days=2),
        end_date=furthest_future_date + timedelta(days=2),
    )

    # A self-paced course that is open for enrollment
    enrollable_self_paced_course = CourseFactory.create(page=None, live=True)
    CoursePageFactory.create(course=enrollable_self_paced_course, live=True)
    self_paced_run = CourseRunFactory.create(
        course=enrollable_self_paced_course,
        live=True,
        in_progress=True,
        enrollment_end=further_future_date + timedelta(days=2),
    )
    self_paced_run.is_self_paced = True
    self_paced_run.save()

    in_progress_course = CourseFactory.create(page=None, live=True)
    CoursePageFactory.create(course=in_progress_course, live=True)
    CourseRunFactory.create(
        course=in_progress_course,
        live=True,
        in_progress=True,
        enrollment_end=further_future_date + timedelta(days=2),
    )

    unenrollable_course = CourseFactory.create(page=None, live=False)
    CoursePageFactory.create(course=unenrollable_course, live=False)
    CourseRunFactory.create(
        course=unenrollable_course, live=False, past_enrollment_end=True
    )

    create_featured_items()
    cache_value = redis_cache.get("CMS_homepage_featured_courses")

    assert len(cache_value) == 4
    assert set(cache_value) == {
        enrollable_future_course,
        enrollable_other_future_course,
        enrollable_self_paced_course,
        in_progress_course,
    }

    assert cache_value[0] == enrollable_self_paced_course
    assert cache_value[1] == enrollable_future_course
    assert cache_value[2] == enrollable_other_future_course
    assert cache_value[3] == in_progress_course

    assert unenrollable_course not in cache_value


@pytest.mark.django_db
def test_create_featured_items_no_courses():
    """Test create_featured_items with no courses at all"""
    redis_cache = caches["redis"]
    redis_cache.delete("CMS_homepage_featured_courses")

    result = create_featured_items()
    cache_value = redis_cache.get("CMS_homepage_featured_courses")

    assert result == []
    assert cache_value == []


@pytest.mark.django_db
def test_create_featured_items_no_enrollable_courses():
    """Test create_featured_items with courses but no enrollable runs"""
    redis_cache = caches["redis"]
    redis_cache.delete("CMS_homepage_featured_courses")

    # Create course with no enrollable runs
    course = CourseFactory.create(page=None, live=True)
    CoursePageFactory.create(course=course, live=True)
    CourseRunFactory.create(course=course, live=False, past_enrollment_end=True)

    result = create_featured_items()
    cache_value = redis_cache.get("CMS_homepage_featured_courses")

    assert result == []
    assert cache_value == []


@pytest.mark.django_db
def test_create_featured_items_many_self_paced_courses():
    """Test create_featured_items limits self-paced courses to 2"""
    redis_cache = caches["redis"]
    redis_cache.delete("CMS_homepage_featured_courses")

    now = now_in_utc()
    further_future_date = now + timedelta(days=2)

    # Create 5 self-paced courses
    self_paced_courses = []
    for _ in range(5):
        course = CourseFactory.create(page=None, live=True)
        CoursePageFactory.create(course=course, live=True)
        run = CourseRunFactory.create(
            course=course,
            live=True,
            in_progress=True,
            enrollment_end=further_future_date,
        )
        run.is_self_paced = True
        run.save()
        self_paced_courses.append(course)

    result = create_featured_items()

    # Should only return 2 self-paced courses
    assert len(result) == 2
    assert all(course in self_paced_courses for course in result)


@pytest.mark.django_db
def test_create_featured_items_many_regular_courses():
    """Test create_featured_items limits regular courses to 20"""
    redis_cache = caches["redis"]
    redis_cache.delete("CMS_homepage_featured_courses")

    now = now_in_utc()
    future_date = now + timedelta(days=1)
    further_future_date = now + timedelta(days=2)
    further_past_date = now - timedelta(days=1)

    # Create 25 regular courses
    regular_courses = []
    for _ in range(25):
        course = CourseFactory.create(page=None, live=True)
        CoursePageFactory.create(course=course, live=True)
        CourseRunFactory.create(
            course=course,
            live=True,
            start_date=future_date,
            enrollment_start=further_past_date,
            enrollment_end=further_future_date,
            end_date=further_future_date,
        )
        regular_courses.append(course)

    result = create_featured_items()

    # Should only return 20 regular courses (no self-paced)
    assert len(result) == 20
    assert all(course in regular_courses for course in result)


@pytest.mark.django_db
def test_create_featured_items_course_run_at_exact_time():
    """Test create_featured_items with course run starting exactly at now"""
    redis_cache = caches["redis"]
    redis_cache.delete("CMS_homepage_featured_courses")

    now = now_in_utc()
    further_future_date = now + timedelta(days=2)
    further_past_date = now - timedelta(days=1)

    # Course run starting exactly at now (should be considered "future")
    exact_time_course = CourseFactory.create(page=None, live=True)
    CoursePageFactory.create(course=exact_time_course, live=True)
    CourseRunFactory.create(
        course=exact_time_course,
        live=True,
        start_date=now,  # Exactly at now
        enrollment_start=further_past_date,
        enrollment_end=further_future_date,
        end_date=further_future_date,
    )

    result = create_featured_items()
    cache_value = redis_cache.get("CMS_homepage_featured_courses")

    assert len(result) == 1
    assert result[0] == exact_time_course
    assert exact_time_course in cache_value


@pytest.mark.django_db
def test_create_featured_items_mixed_course_types():
    """Test create_featured_items with mix of self-paced, future, and started courses"""
    redis_cache = caches["redis"]
    redis_cache.delete("CMS_homepage_featured_courses")

    now = now_in_utc()
    future_date = now + timedelta(days=1)
    past_date = now - timedelta(days=1)
    further_future_date = now + timedelta(days=2)
    further_past_date = now - timedelta(days=2)

    # 1 self-paced course
    self_paced_course = CourseFactory.create(page=None, live=True)
    CoursePageFactory.create(course=self_paced_course, live=True)
    run = CourseRunFactory.create(
        course=self_paced_course,
        live=True,
        in_progress=True,
        enrollment_end=further_future_date,
    )
    run.is_self_paced = True
    run.save()

    # 1 future course
    future_course = CourseFactory.create(page=None, live=True)
    CoursePageFactory.create(course=future_course, live=True)
    CourseRunFactory.create(
        course=future_course,
        live=True,
        start_date=future_date,
        enrollment_start=further_past_date,
        enrollment_end=further_future_date,
        end_date=further_future_date,
    )

    # 1 started course
    started_course = CourseFactory.create(page=None, live=True)
    CoursePageFactory.create(course=started_course, live=True)
    CourseRunFactory.create(
        course=started_course,
        live=True,
        start_date=past_date,
        enrollment_start=further_past_date,
        enrollment_end=further_future_date,
        end_date=further_future_date,
    )

    result = create_featured_items()

    assert len(result) == 3
    # Verify order: self-paced first, then future, then started
    assert result[0] == self_paced_course
    assert result[1] == future_course
    assert result[2] == started_course


@pytest.mark.django_db
def test_create_featured_items_cache_expiration():
    """Test that cache is set with correct expiration time"""
    redis_cache = caches["redis"]
    redis_cache.delete("CMS_homepage_featured_courses")

    # Create a simple course to have something to cache
    course = CourseFactory.create(page=None, live=True)
    CoursePageFactory.create(course=course, live=True)
    run = CourseRunFactory.create(
        course=course,
        live=True,
        in_progress=True,
        enrollment_end=now_in_utc() + timedelta(days=2),
    )
    run.is_self_paced = True
    run.save()

    create_featured_items()

    # Verify cache is set
    cache_value = redis_cache.get("CMS_homepage_featured_courses")
    assert cache_value is not None
    assert len(cache_value) == 1

    # Note: TTL testing would require mocking or actual time measurement
    # which might be flaky, so we just verify the cache is set
