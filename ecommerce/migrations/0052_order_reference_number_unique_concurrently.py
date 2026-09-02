"""
Retired: this migration is intentionally a no-op.

It originally added a unique constraint on Order.reference_number to back the
reference-number order lookup from #3899. That change is reverted, so there is
nothing left to add - and 0053 drops the constraint from any database that
already has it.

The file has to stay. It shipped as
0049_order_reference_number_unique_concurrently and was renamed to 0052 in #3908
to resolve a leaf conflict, which left two populations of databases:

  - migrated before the rename: django_migrations records the 0049 name, and the
    constraint is already on the table
  - migrated after the rename, or created fresh: 0052 is recorded as applied

Deleting the file would strand the second group with an orphan history row, and
keeping the original body would break the first - Django replays 0052 as
unapplied there and "ADD CONSTRAINT ... USING INDEX" fails with "index is
already associated with a constraint". Emptying it satisfies both: the replay
does nothing, and 0053 handles the leftover constraint either way.

Also nothing in state_operations, so migration state carries no constraint for
either population and matches the reverted Order model.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("ecommerce", "0051_refund_reason_choices_from_design"),
    ]

    operations = []
