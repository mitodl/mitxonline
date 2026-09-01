"""
Add the unique constraint on Order.reference_number, building it concurrently.

AddConstraint for a plain UniqueConstraint emits

    ALTER TABLE ecommerce_order ADD CONSTRAINT ... UNIQUE (reference_number);

which holds ACCESS EXCLUSIVE on ecommerce_order for the whole index build -
measured at ~3s over 537k rows. An ACCESS EXCLUSIVE request also queues behind
any in-flight transaction and blocks everything arriving after it, so one slow
query at deploy time turns that into an outage.

Build the index with CONCURRENTLY instead and then attach it to the constraint.
ADD CONSTRAINT ... USING INDEX is a catalog-only operation: it adopts the index
that already exists rather than rebuilding it, which drops the ACCESS EXCLUSIVE
window from ~3s to ~3ms at the same row count.

The end state is byte-for-byte what AddConstraint would have produced - a
UNIQUE constraint backed by a unique btree index of the same name - so a future
migration that alters or drops it lines up with what is actually here.

Recovery: CREATE INDEX CONCURRENTLY leaves an INVALID index behind if it fails
(most likely on a duplicate reference_number). Re-running this migration will
not fix that - IF NOT EXISTS sees the invalid index and skips the build, and the
ADD CONSTRAINT then fails because the index is not valid. Drop it first:

    DROP INDEX CONCURRENTLY unique_order_reference_number;

then resolve the duplicates and re-run.
"""

from django.db import migrations, models

CONSTRAINT_NAME = "unique_order_reference_number"


class Migration(migrations.Migration):
    # CREATE INDEX CONCURRENTLY cannot run inside a transaction block.
    atomic = False

    dependencies = [
        ("ecommerce", "0048_backfill_line_discounted_unit_price"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                # Each statement is its own RunSQL so that neither gets bundled
                # into an implicit transaction block.
                migrations.RunSQL(
                    sql=(
                        f"CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS {CONSTRAINT_NAME} "
                        f"ON ecommerce_order (reference_number)"
                    ),
                    reverse_sql=f"DROP INDEX CONCURRENTLY IF EXISTS {CONSTRAINT_NAME}",
                ),
                migrations.RunSQL(
                    sql=(
                        f"ALTER TABLE ecommerce_order ADD CONSTRAINT {CONSTRAINT_NAME} "
                        f"UNIQUE USING INDEX {CONSTRAINT_NAME}"
                    ),
                    # Dropping the constraint drops the index it adopted, so the
                    # reverse of the statement above becomes a no-op.
                    reverse_sql=(
                        f"ALTER TABLE ecommerce_order "
                        f"DROP CONSTRAINT IF EXISTS {CONSTRAINT_NAME}"
                    ),
                ),
            ],
            state_operations=[
                migrations.AddConstraint(
                    model_name="order",
                    constraint=models.UniqueConstraint(
                        fields=["reference_number"], name=CONSTRAINT_NAME
                    ),
                ),
            ],
        ),
    ]
