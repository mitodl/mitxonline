import logging
from urllib.parse import urljoin, urlparse

import requests
from django.core.cache import cache
from mitol.common.decorators import single_task

from cms.api import create_featured_items
from cms.models import Page
from main.celery import app
from main.settings import (
    MITX_ONLINE_FASTLY_AUTH_TOKEN,
    MITX_ONLINE_FASTLY_URL,
    SITE_BASE_URL,
)


def call_fastly_purge_api(relative_url):
    """
    Calls the Fastly purge API. (We aren't using the official Fastly SDK here
    because it doesn't work for this - the version of it that works with the
    current API only allows you to purge *everything*, not individual pages.)

    Args:
        - relative_url  The relative URL to purge.
    Returns:
        - Dict of the response (resp.json), or False if there was an error.
    """
    logger = logging.getLogger("fastly_purge")

    (scheme, netloc, path, params, query, fragment) = urlparse(SITE_BASE_URL)

    headers = {"host": netloc}

    if relative_url != "*":
        headers["fastly-soft-purge"] = "1"

    if MITX_ONLINE_FASTLY_AUTH_TOKEN:
        headers["fastly-key"] = MITX_ONLINE_FASTLY_AUTH_TOKEN

    api_url = urljoin(MITX_ONLINE_FASTLY_URL, relative_url)

    resp = requests.request("PURGE", api_url, headers=headers)

    if resp.status_code >= 400:  # noqa: PLR2004
        logger.error(f"Fastly API Purge call failed: {resp.status_code} {resp.reason}")  # noqa: G004
        logger.error(f"Fastly returned: {resp.text}")  # noqa: G004
        return False
    else:
        logger.info(f"Fastly returned: {resp.text}")  # noqa: G004
        return resp.json()


@app.task
def queue_fastly_purge_url(page_id):
    """
    Purges the given page_id from the Fastly cache. This should happen on a
    handful of Wagtail signals:
    - page_published
    - page_unpublished
    - post_page_move
    """
    logger = logging.getLogger("fastly_purge")

    logger.info(f"Processing purge request for {page_id}")  # noqa: G004

    page = Page.objects.get(pk=page_id)

    logger.debug(f"Page URL is {page.get_url()}")  # noqa: G004

    if page is None:
        raise Exception(f"Page {page_id} not found.")  # noqa: EM102, TRY002

    resp = call_fastly_purge_api(page.get_url())

    if resp and resp["status"] == "ok":
        logger.info("Purge request processed OK.")
        return True

    logger.error("Purge request failed.")  # noqa: RET503


@app.task()
def queue_fastly_full_purge():
    """
    Purges everything from the Fastly cache.

    Passing * to the purge API instructs Fastly to purge everything.
    """
    logger = logging.getLogger("fastly_purge")

    logger.info("Purging all pages from the Fastly cache...")

    resp = call_fastly_purge_api("*")

    if resp and resp["status"] == "ok":
        logger.info("Purge request processed OK.")
        return True

    logger.error("Purge request failed.")  # noqa: RET503


@app.task
@single_task(10)
def refresh_featured_homepage_items():
    """
    Refresh the featured homepage items in the memcached cache.
    """
    logger = logging.getLogger("refresh_featured_homepage_items__task")
    logger.info("Refreshing featured homepage items...")
    featured_courses = cache.get("CMS_homepage_featured_courses")
    if featured_courses is not None:
        logger.info("Featured courses found in cache, moving on")
        return
    logger.info("No featured courses found in cache, refreshing")
    create_featured_items()
    logger.info("New featured items created")
