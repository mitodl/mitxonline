import logging

from wagtail.signals import page_published

from cms.models import FlexiblePricingRequestForm
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


page_published.connect(flex_pricing_field_check)
