from django.db import migrations

from ecommerce.db_utils import create_delete_rule, rollback_delete_rule


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
    ]
