"""API functionality for the CMS app"""
import logging
from typing import Tuple
from urllib.parse import urljoin, urlencode

from django.conf import settings
from django.contrib.contenttypes.models import ContentType

from django.utils.text import slugify
from wagtail.core.blocks import StreamValue
from wagtail.core.models import Page, Site

from cms import models as cms_models
from cms.exceptions import WagtailSpecificPageError

log = logging.getLogger(__name__)
DEFAULT_HOMEPAGE_PROPS = dict(
    title="Home Page",
    hero_title="Lorem ipsum dolor",
    hero_subtitle="Enim ad minim veniam, quis nostrud exercitation",
)
DEFAULT_SITE_PROPS = dict(hostname="localhost", port=80)
COURSE_INDEX_PAGE_PROPERTIES = dict(title="Courses")
RESOURCE_PAGE_TITLES = [
    "About Us",
    "Terms of Service",
    "Privacy Policy",
    "Honor Code",
]
RESOURCE_PAGE_SLUGS = [slugify(title) for title in RESOURCE_PAGE_TITLES]


def get_home_page(raise_if_missing=True, check_specific=False) -> Page:
    """
    Returns an instance of the home page (all of our Wagtail pages are expected to be descendants of this home page)

    Returns:
        Page: The home page object
    """
    home_page = Page.objects.filter(
        content_type=ContentType.objects.get_for_model(cms_models.HomePage), live=True
    ).first()
    if raise_if_missing is True and home_page is None:
        raise Page.DoesNotExist
    if check_specific and home_page is not None:
        try:
            home_page.get_specific()
        except cms_models.HomePage.DoesNotExist as exc:
            raise WagtailSpecificPageError(
                spec_page_cls=cms_models.HomePage, page_obj=home_page
            ) from exc
    return home_page


def _create_resource_page(title: str) -> cms_models.ResourcePage:
    """Creates a resource page with the given title under the parent page"""
    return cms_models.ResourcePage(
        slug=slugify(title),
        title=title,
        content=StreamValue(
            "content",
            [
                {
                    "type": "content",
                    "value": {
                        "heading": title,
                        "detail": f"<p>Stock {title.lower()} page.</p>",
                    },
                }
            ],
            is_lazy=True,
        ),
    )


def ensure_resource_pages() -> None:
    """
    Ensures that a set of specific resource pages exist in some basic form
    """
    home_page = get_home_page()
    resource_pages_qset = cms_models.ResourcePage.objects.filter(
        slug__in=RESOURCE_PAGE_SLUGS
    )
    if resource_pages_qset.count() == len(RESOURCE_PAGE_SLUGS):
        return
    existing_resource_titles = set(resource_pages_qset.values_list("title", flat=True))
    missing_resource_titles = set(RESOURCE_PAGE_TITLES) - existing_resource_titles
    for resource_page_title in missing_resource_titles:
        resource_page = _create_resource_page(resource_page_title)
        home_page.add_child(instance=resource_page)
        resource_page.save_revision().publish()


def ensure_home_page_and_site() -> Tuple[cms_models.HomePage, Site]:
    """
    Ensures that Wagtail is configured with a home page of the right type, and that
    the home page is configured as the default site.
    """
    site = Site.objects.filter(is_default_site=True).first()
    home_page = get_home_page(raise_if_missing=False, check_specific=True)
    root = Page.objects.get(depth=1)
    if home_page is None:
        home_page = cms_models.HomePage(**DEFAULT_HOMEPAGE_PROPS)
        root.add_child(instance=home_page)
        home_page.refresh_from_db()
        specific_home_page = home_page
    else:
        specific_home_page = home_page.specific
    if site is None:
        Site.objects.create(
            is_default_site=True, root_page=home_page, **DEFAULT_SITE_PROPS
        )
    elif site.root_page is None or site.root_page != home_page:
        site.root_page = home_page
        site.save()
        log.info("Updated site: %s", site)
    wagtail_default_home_page = Page.objects.filter(
        depth=2, content_type=ContentType.objects.get_for_model(Page)
    ).first()
    if wagtail_default_home_page is not None:
        wagtail_default_home_page.delete()
    return specific_home_page, site


def ensure_product_index() -> cms_models.CourseIndexPage:
    """
    Ensures that an index page has been created for each type of product, and that all product pages are
    nested under it.
    """
    home_page = get_home_page()
    course_index = Page.objects.filter(
        content_type=ContentType.objects.get_for_model(cms_models.CourseIndexPage)
    ).first()
    if not course_index:
        course_index = cms_models.CourseIndexPage(**COURSE_INDEX_PAGE_PROPERTIES)
        home_page.add_child(instance=course_index)
        course_index.save_revision().publish()
    # Move course detail pages to be children of the course index pages
    for page_id in cms_models.CoursePage.objects.exclude(
        path__startswith=course_index.path
    ).values_list("id", flat=True):
        page = Page.objects.get(id=page_id)
        page.move(course_index, "last-child")
    return course_index


def get_wagtail_img_src(image_obj) -> str:
    """Returns the image source URL for a Wagtail Image object"""
    return (
        "{url}?{qs}".format(
            url=urljoin(settings.MEDIA_URL, image_obj.file.name),
            qs=urlencode({"v": image_obj.file_hash}),
        )
        if image_obj
        else ""
    )
