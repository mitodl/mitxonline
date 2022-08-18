from main.celery import app
from main.settings import (
    SITE_BASE_URL,
    MITX_ONLINE_FASTLY_AUTH_TOKEN,
    MITX_ONLINE_FASTLY_URL,
)
from cms.models import Page
from urllib.parse import urljoin, urlparse
import fastly
import logging


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

    if page is None:
        raise Exception(f"Page {page_id} not found.")

    (scheme, netloc, path, params, query, fragment) = urlparse(SITE_BASE_URL)

    api = fastly.API()

    if MITX_ONLINE_FASTLY_AUTH_TOKEN is not None:
        api.authenticate_by_key(MITX_ONLINE_FASTLY_AUTH_TOKEN)

    target_url = urljoin(MITX_ONLINE_FASTLY_URL, page.get_url())

    try:
        if not api.purge_url(netloc, target_url, soft=True):
            logger.error(f"Fastly purge of {page.title} failed.")
    except fastly.errors.AuthenticationError:
        logger.error(f"Fastly purge of {page.title} failed: authenticaiton error")
    except fastly.errors.InternalServerError:
        logger.error(f"Fastly purge of {page.title} failed: internal server error")
    except fastly.errors.BadRequestError as e:
        logger.error(f"Fastly purge of {page.title} failed: bad request. {e}")
    except fastly.errors.NotFoundError:
        logger.error(f"Fastly purge of {page.title} failed: not found")
    except:
        logger.error(f"Fastly purge of {page.title} failed: threw a generic exception")
