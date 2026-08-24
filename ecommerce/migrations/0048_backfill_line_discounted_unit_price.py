"""
Backfill Line.discounted_unit_price for orders where the price is exactly
recoverable from Order.total_price_paid.

Two rules, both exact. Everything else is left NULL and keeps recomputing on
read: a discounted total spread across several lines cannot be split back
apart without knowing the discount that produced it.

total_price_paid is written by the pricing pass, not at fulfillment, so it is
populated and meaningful on orders in any state.
"""

import json
import logging
from decimal import Decimal

from django.db import migrations
from django.db.models import Count

log = logging.getLogger(__name__)

BATCH_SIZE = 2000


def _list_price(line):
    """The line's product price as of the version it was purchased at."""
    fields = json.loads(line.product_version.serialized_data)[0]["fields"]
    return Decimal(str(fields["price"]))


def _derivable(lines, Order, Line):
    """Return the (line, value) pairs this batch can fill exactly."""
    order_ids = {line.order_id for line in lines}
    totals = dict(
        Order.objects.filter(pk__in=order_ids).values_list("pk", "total_price_paid")
    )
    line_counts = dict(
        Line.objects.filter(order_id__in=order_ids)
        .values_list("order_id")
        .annotate(count=Count("id"))
    )

    filled = []
    for line in lines:
        total = totals.get(line.order_id)
        if total is None:
            continue

        # Rule 1: no line can be negative, so a zero total means every line
        # was free.
        if total == 0:
            filled.append((line, Decimal(0)))
            continue

        # Rule 2: a single line at quantity 1 cost exactly the order total.
        # A discounted price never exceeds the list price, so a total above it
        # covers something this line does not account for -- two Products for
        # the same purchasable object collapse into one Line but are summed
        # twice into the total. Those orders stay NULL.
        if (
            total > 0
            and line.quantity == 1
            and line_counts.get(line.order_id) == 1
            and total <= _list_price(line)
        ):
            filled.append((line, total))

    return filled


def backfill_discounted_unit_price(apps, schema_editor):
    """Fill the two exactly-derivable cases; leave everything else NULL."""
    Line = apps.get_model("ecommerce", "Line")
    Order = apps.get_model("ecommerce", "Order")

    filled_count = 0
    skipped_count = 0
    last_pk = 0

    while True:
        batch = list(
            Line.objects.filter(pk__gt=last_pk, discounted_unit_price__isnull=True)
            .select_related("product_version")
            .order_by("pk")[:BATCH_SIZE]
        )
        if not batch:
            break
        last_pk = batch[-1].pk

        filled = _derivable(batch, Order, Line)
        for line, value in filled:
            line.discounted_unit_price = value
        Line.objects.bulk_update(
            [line for line, _ in filled], ["discounted_unit_price"]
        )

        filled_count += len(filled)
        skipped_count += len(batch) - len(filled)

    log.info(
        "Backfilled Line.discounted_unit_price: %s filled, %s left null",
        filled_count,
        skipped_count,
    )


class Migration(migrations.Migration):
    # Each batch commits on its own: one transaction over every backfilled row
    # would hold write locks that live checkout blocks on.
    atomic = False

    dependencies = [
        ("ecommerce", "0047_line_discounted_unit_price"),
    ]

    operations = [
        migrations.RunPython(
            backfill_discounted_unit_price,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
