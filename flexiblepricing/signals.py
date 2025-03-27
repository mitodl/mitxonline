"""
Signals for mitxonline course certificates
"""

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

from flexiblepricing.constants import FlexiblePriceStatus
from flexiblepricing.models import FlexiblePrice
from flexiblepricing.tasks import process_flexible_price_discount_task


logger = logging.getLogger(__name__)


@receiver(post_save, sender=FlexiblePrice, dispatch_uid="flexibleprice_post_save")
def handle_flexible_price_save(sender, instance, created, **kwargs):  # pylint: disable=unused-argument  # noqa: ARG001
    """Orchestrate the flexible price processing workflow."""
    if not _should_process_flexible_price(instance):
        return

    # call the process_flexible_price_discount task
    process_flexible_price_discount_task.delay(instance.id)


def _should_process_flexible_price(instance) -> bool:
    """Check if the instance meets basic processing criteria."""
    return instance.status in (
        FlexiblePriceStatus.APPROVED,
        FlexiblePriceStatus.AUTO_APPROVED,
    )
