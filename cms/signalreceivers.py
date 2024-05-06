import logging

from wagtail.signals import page_published, page_unpublished, post_page_move

from cms.models import FlexiblePricingRequestForm
from cms.tasks import queue_fastly_purge_url
from flexiblepricing.utils import ensure_flexprice_form_fields

logger = logging.getLogger("cms.signalreceiver")


def fastly_purge_url_receiver(sender, **kwargs):  # noqa: ARG001
    """
    Generic receiver for the Wagtail page_published, page_unpublished, and
    post_page_move signals. The most important part of the kwargs passed in all
    of these is the page instance so we can use the same receiver for all of them.

    For post_page_move, we also look for the url_path_before arg and only
    process this if the path_before and path_after are different.
    """
    instance = kwargs["instance"]

    if "url_path_before" in kwargs:  # noqa: SIM102
        if kwargs["url_path_before"] == kwargs["url_path_after"]:
            return

    logger.info(f"Queueing Fastly purge for {instance.id} - {instance.title}")  # noqa: G004

    queue_fastly_purge_url.delay(instance.id)


def flex_pricing_field_check(sender, **kwargs):  # noqa: ARG001
    """
    Receives the Wagtail page_published signal and, if it's for a flexible
    pricing request form, ensures the form has the two fields required to make
    this work:
    - Your Income (a Number field)
    - Income Currency (a Country field)

    If these fields exist with these names, it will leave them alone. If the
    fields don't exist, it will create new ones and append them to the form. If
    there are fields "in between" (name or type matches but not both), we'll
    log an error.
    """
    instance = kwargs["instance"]

    if isinstance(instance, FlexiblePricingRequestForm):
        logger.info(
            f"Checking fields for Flexible Pricing Request Form {instance.id} - {instance.title}"  # noqa: G004
        )

        if ensure_flexprice_form_fields(instance):
            logger.info("Form was OK!")
        else:
            logger.info("Form changed (or needs changes)")


page_published.connect(fastly_purge_url_receiver)
page_unpublished.connect(fastly_purge_url_receiver)
post_page_move.connect(fastly_purge_url_receiver)

page_published.connect(flex_pricing_field_check)
