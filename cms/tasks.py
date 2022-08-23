from main.celery import app
from main.settings import (
    SITE_BASE_URL,
    MITX_ONLINE_FASTLY_AUTH_TOKEN,
    MITX_ONLINE_FASTLY_URL,
)
from cms.models import Page
from urllib.parse import urljoin, urlparse
import logging
import requests


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

    if resp.status_code >= 400:
        logger.error(f"Fastly API Purge call failed: {resp.status_code} {resp.reason}")
        logger.error(f"Fastly returned: {resp.text}")
        return False
    else:
        logger.info(f"Fastly returned: {resp.text}")
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

    logger.info(f"Processing purge request for {page_id}")

    page = Page.objects.get(pk=page_id)

    logger.debug(f"Page URL is {page.get_url()}")

    if page is None:
        raise Exception(f"Page {page_id} not found.")

    resp = call_fastly_purge_api(page.get_url())

    if resp and resp["status"] == "ok":
        logger.info("Purge request processed OK.")
        return True

    logger.error("Purge request failed.")


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

    logger.error("Purge request failed.")
