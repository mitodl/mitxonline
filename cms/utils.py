from django.conf import settings
from django.urls import reverse

from cms.constants import FEATURED_ITEMS_CACHE_KEY


def get_page_editing_url(page_id: int) -> str:
    """
    Return the URL for editing a Wagtail page with the given ID.
    """
    return (
        f"{settings.SITE_BASE_URL.rstrip('/')}"
        f"{reverse('wagtailadmin_pages:edit', args=[page_id])}"
    )


def get_featured_items_cache_key():
    """Return the cache key used to store the CMS homepage's featured items"""
    return FEATURED_ITEMS_CACHE_KEY
