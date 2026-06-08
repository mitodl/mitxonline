import logging

from django.db import transaction
from wagtail.signals import page_published

from cms.models import CoursePage, FlexiblePricingRequestForm, ProgramPage
from cms.tasks import queue_fastly_surrogate_key_purge
from flexiblepricing.utils import ensure_flexprice_form_fields

logger = logging.getLogger("cms.signalreceiver")


def flex_pricing_field_check(sender, **kwargs):  # noqa: ARG001
    """
    Receives the Wagtail page_published signal and, if it's for a flexible
    pricing request form, ensures the form has the fields required to make
    this work.

    If the fields exist with correct name/type names, it will leave them alone. If the
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


def purge_fastly_cache_on_publish(sender, **kwargs):  # noqa: ARG001
    """
    Receives the Wagtail page_published signal and purges the corresponding
    Fastly surrogate key so that MIT Learn product pages are invalidated.

    Key format:
        CoursePage   -> mitxonline:course:<readable_id>
        ProgramPage  -> mitxonline:program:<readable_id>
    """
    instance = kwargs["instance"]

    if isinstance(instance, CoursePage):
        surrogate_key = f"mitxonline:course:{instance.course.readable_id}"
    elif isinstance(instance, ProgramPage):
        surrogate_key = f"mitxonline:program:{instance.program.readable_id}"
    else:
        return

    logger.info(
        "Scheduling Fastly surrogate key purge on page publish: %s", surrogate_key
    )
    transaction.on_commit(lambda: queue_fastly_surrogate_key_purge.delay(surrogate_key))


page_published.connect(flex_pricing_field_check)
page_published.connect(purge_fastly_cache_on_publish)
