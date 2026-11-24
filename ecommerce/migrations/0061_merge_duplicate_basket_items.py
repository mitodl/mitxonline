"""
Merge basket items that hold the same product in the same basket.

Some add-to-basket paths used to create a new row even when the product was
already in the basket. The next migration makes (basket, product) unique, so
fold each set of duplicates into its oldest row first.

Duplicates come from adding the same product again, not from wanting more of
it, so the merged row keeps the largest quantity rather than the sum. It keeps
its own contract, or takes the first contract a duplicate had.
"""

from django.db import migrations
from django.db.models import Count, Max


def merge_duplicate_basket_items(apps, schema_editor):
    BasketItem = apps.get_model("ecommerce", "BasketItem")

    duplicates = (
        BasketItem.objects.values("basket_id", "product_id")
        .annotate(count=Count("id"), max_quantity=Max("quantity"))
        .filter(count__gt=1)
    )

    for duplicate in duplicates:
        items = list(
            BasketItem.objects.filter(
                basket_id=duplicate["basket_id"], product_id=duplicate["product_id"]
            ).order_by("id")
        )
        keep, *extras = items

        keep.quantity = duplicate["max_quantity"]
        if keep.b2b_contract_id is None:
            keep.b2b_contract_id = next(
                (item.b2b_contract_id for item in extras if item.b2b_contract_id),
                None,
            )
        keep.save(update_fields=["quantity", "b2b_contract"])

        BasketItem.objects.filter(pk__in=[item.pk for item in extras]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("ecommerce", "0060_add_user_location_to_basket_and_order"),
    ]

    operations = [
        migrations.RunPython(
            merge_duplicate_basket_items, reverse_code=migrations.RunPython.noop
        ),
    ]
