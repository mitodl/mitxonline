"""
Drop the leftover unique constraint on Order.reference_number.

The constraint came in with #3899 to back the reference-number order lookup on
the CyberSource callback. That change is reverted, so the constraint goes with
it. 0052 - which created it - is now a no-op, so this migration exists purely to
clean up databases that ran the original version of it under either name.

Database-only: 0052 no longer adds the constraint to migration state, so there
is no state to remove here, and every statement is guarded to be a no-op on a
database that never had it.

DROP CONSTRAINT is catalog-only and takes the index it adopted with it, so the
ACCESS EXCLUSIVE window is ~3ms rather than the ~3s an index rebuild would cost
at 537k rows.
"""

from django.db import migrations

CONSTRAINT_NAME = "unique_order_reference_number"


class Migration(migrations.Migration):
    # DROP INDEX CONCURRENTLY cannot run inside a transaction block.
    atomic = False

    dependencies = [
        ("ecommerce", "0052_order_reference_number_unique_concurrently"),
    ]

    operations = [
        # Each statement is its own RunSQL so that neither gets bundled into an
        # implicit transaction block. Both reverse to a no-op: there is no
        # earlier migration that creates this constraint anymore, so rolling
        # back past here should leave it absent.
        migrations.RunSQL(
            sql=(
                f"ALTER TABLE ecommerce_order "
                f"DROP CONSTRAINT IF EXISTS {CONSTRAINT_NAME}"
            ),
            reverse_sql=migrations.RunSQL.noop,
        ),
        # Covers a database where the original 0052's CREATE INDEX CONCURRENTLY
        # left an index that ADD CONSTRAINT never adopted (including an INVALID
        # one from a failed build). A no-op otherwise - the DROP CONSTRAINT
        # above already took the index with it.
        migrations.RunSQL(
            sql=f"DROP INDEX CONCURRENTLY IF EXISTS {CONSTRAINT_NAME}",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
