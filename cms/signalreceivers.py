from wagtail.core.signals import page_published, page_unpublished, post_page_move
from cms.tasks import queue_fastly_purge_url
import logging


def fastly_purge_url_receiver(sender, **kwargs):
    """
    Generic receiver for the Wagtail page_published, page_unpublished, and
    post_page_move signals. The most important part of the kwargs passed in all
    of these is the page instance so we can use the same receiver for all of them.

    For post_page_move, we also look for the url_path_before arg and only
    process this if the path_before and path_after are different.
    """
    logger = logging.getLogger("cms.signalreceiver")

    instance = kwargs["instance"]

    if "url_path_before" in kwargs:
        if kwargs["url_path_before"] == kwargs["url_path_after"]:
            return

    logger.info(f"Queueing Fastly purge for {instance.id} - {instance.title}")

    queue_fastly_purge_url.delay(instance.id)


page_published.connect(fastly_purge_url_receiver)
page_unpublished.connect(fastly_purge_url_receiver)
post_page_move.connect(fastly_purge_url_receiver)
