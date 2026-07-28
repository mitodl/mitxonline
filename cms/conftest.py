"""Fixtures for CMS test suite"""

from types import SimpleNamespace

import pytest

from cms.api import ensure_home_page_and_site, ensure_product_index
from cms.constants import FEATURED_ITEMS_CACHE_KEY


@pytest.fixture(autouse=True)
def isolate_featured_items_cache_key(mocker, worker_id):
    """
    Give each xdist worker its own featured items cache key.

    Tests exercise the real CMS_homepage_featured_courses Redis key, and
    several of them delete/set/get it directly. Since all workers in a run
    share one Redis instance, two such tests landing on different workers
    at the same time race on that key. Suffixing by worker_id (e.g. "gw0",
    "master" outside xdist) gives each worker its own key.
    """
    mocker.patch(
        "cms.utils.get_featured_items_cache_key",
        return_value=f"{FEATURED_ITEMS_CACHE_KEY}_{worker_id}",
    )


@pytest.fixture
def configured_wagtail_home():
    """Fixture that ensures the site and home page are correctly configured"""
    home_page, site = ensure_home_page_and_site()
    return SimpleNamespace(home_page=home_page, site=site)


@pytest.fixture
def fully_configured_wagtail(configured_wagtail_home):
    """Fixture that ensures the site home page, and index pages are correctly configured"""
    course_index_page = ensure_product_index()
    return SimpleNamespace(
        home_page=configured_wagtail_home.home_page,
        site=configured_wagtail_home.site,
        course_index_page=course_index_page,
    )
