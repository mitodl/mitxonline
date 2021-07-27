"""API functionality for the CMS app"""
import logging
from urllib.parse import urljoin, urlencode

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from wagtail.core.models import Page, Site

from cms import models as cms_models

log = logging.getLogger(__name__)
DEFAULT_HOMEPAGE_PROPS = dict(
    title="Home Page",
    hero_title="Lorem ipsum dolor",
    hero_subtitle="Enim ad minim veniam, quis nostrud exercitation",
)
DEFAULT_SITE_PROPS = dict(hostname="localhost", port=80)


def get_home_page():
    """
    Returns an instance of the home page (all of our Wagtail pages are expected to be descendants of this home page)

    Returns:
        Page: The home page object
    """
    return Page.objects.get(
        content_type=ContentType.objects.get_for_model(cms_models.HomePage)
    )


def ensure_home_page_and_site():
    """
    Ensures that Wagtail is configured with a home page of the right type, and that
    the home page is configured as the default site.
    """
    site = Site.objects.filter(is_default_site=True).first()
    valid_home_page = Page.objects.filter(
        content_type=ContentType.objects.get_for_model(cms_models.HomePage)
    ).first()
    root = Page.objects.get(depth=1)
    if valid_home_page is None:
        valid_home_page = cms_models.HomePage(**DEFAULT_HOMEPAGE_PROPS)
        root.add_child(instance=valid_home_page)
        valid_home_page.refresh_from_db()
    if site is None:
        Site.objects.create(
            is_default_site=True, root_page=valid_home_page, **DEFAULT_SITE_PROPS
        )
    elif site.root_page is None or site.root_page != valid_home_page:
        site.root_page = valid_home_page
        site.save()
        log.info("Updated site: %s", site)
    wagtail_default_home_page = Page.objects.filter(
        depth=2, content_type=ContentType.objects.get_for_model(Page)
    ).first()
    if wagtail_default_home_page is not None:
        wagtail_default_home_page.delete()


def get_wagtail_img_src(image_obj):
    """Returns the image source URL for a Wagtail Image object"""
    return (
        "{url}?{qs}".format(
            url=urljoin(settings.MEDIA_URL, image_obj.file.name),
            qs=urlencode({"v": image_obj.file_hash}),
        )
        if image_obj
        else ""
    )
