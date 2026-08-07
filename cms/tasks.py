import logging
from urllib.parse import urljoin, urlparse

import requests
from django.conf import settings
from mitol.common.decorators import single_task

from cms.api import create_featured_items
from cms.models import Page
from main.celery import app


def call_fastly_purge_api(relative_url):
    """
    Calls the Fastly purge API. (We aren't using the official Fastly SDK here
    because it doesn't work for this - the version of it that works with the
    current API only allows you to purge *everything*, not individual pages.)

    Purges by URL against MITxOnline's own site -- the target is identified by
    the `host` header taken from SITE_BASE_URL, not by a Fastly service ID.

    Args:
        - relative_url  The relative URL to purge.
    Returns:
        - Dict of the response (resp.json), or False if there was an error.
    """
    logger = logging.getLogger("fastly_purge")
    netloc = urlparse(settings.SITE_BASE_URL)[1]

    headers = {"host": netloc}

    if relative_url != "*":
        headers["fastly-soft-purge"] = "1"

    if settings.FASTLY_AUTH_TOKEN:
        headers["fastly-key"] = settings.FASTLY_AUTH_TOKEN

    api_url = urljoin(settings.FASTLY_URL, relative_url)

    resp = requests.request("PURGE", api_url, headers=headers)  # noqa: S113

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
    Purges the given page_id from the Fastly cache.
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

    logger.error("Purge request failed.")
    return False


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
    return False


@app.task
def queue_fastly_surrogate_key_purge(surrogate_key, service_id=None):
    """
    Purges all Fastly cached responses tagged with the given surrogate key.

    Uses the Fastly purge-by-tag API:
    POST /service/{service_id}/purge/{surrogate_key}

    MIT Learn tags its product page responses with the MITxOnline surrogate keys
    they depend on (via the Surrogate-Key response header), which lets MITxOnline
    invalidate those pages when course/program data changes. The service is
    therefore Learn's -- purging MITxOnline's own Fastly service would do nothing,
    since it tags no responses with these keys.

    Key format: mitxonline:course:<readable_id> or mitxonline:program:<readable_id>

    This is a *hard* purge. A soft purge only marks objects stale, so each cache
    node serves the outdated page once more before refreshing. For the events
    this task reacts to -- publishing, unpublishing, flipping `live` -- that
    response is not merely stale but wrong: a cached 404 for a page that now
    exists, or a page that should no longer be reachable.

    Args:
        surrogate_key (str): The surrogate key to purge, e.g.
            "mitxonline:course:course-v1:MITx+6.00.1x"
        service_id (str): The Fastly service ID whose cache should be purged.
            Falls back to settings.MIT_LEARN_FASTLY_SERVICE_ID when omitted.
    """
    logger = logging.getLogger("fastly_purge")

    service_id = service_id or settings.MIT_LEARN_FASTLY_SERVICE_ID

    if not service_id:
        logger.warning(
            "No Fastly service ID given; skipping surrogate key purge for %s. "
            "Is MIT_LEARN_FASTLY_SERVICE_ID set?",
            surrogate_key,
        )
        return False

    if not settings.FASTLY_AUTH_TOKEN:
        logger.warning(
            "FASTLY_AUTH_TOKEN is not set; skipping surrogate key purge for %s",
            surrogate_key,
        )
        return False

    logger.info(
        "Purging Fastly surrogate key %s from service %s", surrogate_key, service_id
    )

    api_url = urljoin(
        settings.FASTLY_URL,
        f"/service/{service_id}/purge/{surrogate_key}",
    )
    headers = {"Fastly-Key": settings.FASTLY_AUTH_TOKEN}

    resp = requests.post(api_url, headers=headers, timeout=10)

    if resp.status_code >= 400:  # noqa: PLR2004
        logger.error(
            "Fastly surrogate key purge failed for %s: %s %s",
            surrogate_key,
            resp.status_code,
            resp.reason,
        )
        logger.error("Fastly returned: %s", resp.text)
        return False

    logger.info("Fastly surrogate key purge OK for %s: %s", surrogate_key, resp.text)
    return True


@app.task
@single_task(30)
def refresh_featured_homepage_items():
    """
    Refresh the featured homepage items in the redis cache.
    """
    logger = logging.getLogger("refresh_featured_homepage_items__task")
    logger.info("Refreshing featured homepage items...")
    create_featured_items()
    logger.info("Featured items refreshed")
