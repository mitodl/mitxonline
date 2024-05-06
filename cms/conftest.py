"""Fixtures for CMS test suite"""

from types import SimpleNamespace

import pytest

from cms.api import ensure_home_page_and_site, ensure_product_index


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
