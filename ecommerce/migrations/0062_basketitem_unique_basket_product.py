"""
Make (basket, product) unique on basket items.

Separate from the data migration that merges duplicates: Postgres won't alter
a table with deferred trigger events pending from that migration's deletes.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ecommerce", "0061_merge_duplicate_basket_items"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="basketitem",
            constraint=models.UniqueConstraint(
                fields=("basket", "product"), name="unique_basket_product"
            ),
        ),
    ]
