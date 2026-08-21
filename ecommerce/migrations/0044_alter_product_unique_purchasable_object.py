from django.db import migrations, models

from ecommerce.db_utils import create_delete_rule, rollback_delete_rule


def deduplicate_products(apps, schema_editor):
    """
    Hard-delete duplicate products sharing the same (object_id, content_type).

    The previous constraint was partial (is_active=True only), so multiple
    inactive products may exist for the same purchasable object. The new
    constraint covers all rows, so duplicates must be removed first.

    Retention priority: active product first, then highest id (most recent).
    """
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            DELETE FROM ecommerce_product
            WHERE id NOT IN (
                SELECT DISTINCT ON (object_id, content_type_id) id
                FROM ecommerce_product
                ORDER BY object_id, content_type_id, is_active DESC, id DESC
            )
            """
        )


class Migration(migrations.Migration):
    table_name = "product"
    dependencies = [
        ("ecommerce", "0043_refund_request_status"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="product",
            name="unique_purchasable_object",
        ),
        migrations.RunSQL(
            sql=rollback_delete_rule(table_name),
            reverse_sql=create_delete_rule(table_name),
        ),
        migrations.RunPython(
            deduplicate_products,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name="product",
            constraint=models.UniqueConstraint(
                fields=("object_id", "content_type"),
                name="unique_purchasable_object",
            ),
        ),
        migrations.RunSQL(
            sql=create_delete_rule(table_name),
            reverse_sql=rollback_delete_rule(table_name),
        ),
    ]
