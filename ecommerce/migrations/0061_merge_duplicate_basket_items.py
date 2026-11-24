"""
Merge basket items that hold the same product in the same basket.

Some add-to-basket paths used to create a new row even when the product was
already in the basket. The next migration makes (basket, product) unique, so
fold each set of duplicates into its oldest row first.

Duplicates come from adding the same product again, not from wanting more of
it, so the merged row keeps the largest quantity rather than the sum.

Rows that disagree on their B2B contract (including one with a contract and
one without) aren't merged: picking one would attribute the purchase to a
contract the learner may not have meant, and checkout refuses such a basket
anyway ("Duplicate products cannot have conflicting contracts."). Those rows
are all removed, so the learner adds the product again under the right
contract.
"""

import logging

from django.db import migrations
from django.db.models import Count

log = logging.getLogger(__name__)


def plan_merge(items):
    """
    Decide what to do with one set of duplicate basket items.

    Args:
    - items: the duplicate rows, oldest first; each has id, quantity and
      b2b_contract_id

    Returns:
    - tuple: (the row to keep or None, its new quantity or None, ids to delete)
    """

    if len({item.b2b_contract_id for item in items}) > 1:
        return None, None, [item.id for item in items]

    keep, *extras = items
    return keep, max(item.quantity for item in items), [item.id for item in extras]


def merge_duplicate_basket_items(apps, schema_editor):
    BasketItem = apps.get_model("ecommerce", "BasketItem")

    duplicates = (
        BasketItem.objects.values("basket_id", "product_id")
        .annotate(count=Count("id"))
        .filter(count__gt=1)
    )

    for duplicate in duplicates:
        items = list(
            BasketItem.objects.filter(
                basket_id=duplicate["basket_id"], product_id=duplicate["product_id"]
            ).order_by("id")
        )
        keep, quantity, delete_ids = plan_merge(items)

        if keep is None:
            log.warning(
                "Removing product %s from basket %s: its %s rows name "
                "different contracts",
                duplicate["product_id"],
                duplicate["basket_id"],
                len(items),
            )
        else:
            keep.quantity = quantity
            keep.save(update_fields=["quantity"])

        BasketItem.objects.filter(pk__in=delete_ids).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("ecommerce", "0060_add_user_location_to_basket_and_order"),
    ]

    operations = [
        migrations.RunPython(
            merge_duplicate_basket_items, reverse_code=migrations.RunPython.noop
        ),
    ]
