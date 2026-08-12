from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ecommerce", "0043_refund_request_status"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="product",
            name="unique_purchasable_object",
        ),
        migrations.AddConstraint(
            model_name="product",
            constraint=models.UniqueConstraint(
                fields=("object_id", "content_type"),
                name="unique_purchasable_object",
            ),
        ),
    ]
