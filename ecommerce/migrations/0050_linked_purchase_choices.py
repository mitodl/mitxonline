from django.db import migrations, models


class Migration(migrations.Migration):
    # Choices changes emit no SQL; this only syncs migration state.

    dependencies = [
        ("ecommerce", "0049_line_discounted_unit_price_not_null"),
    ]

    operations = [
        migrations.AlterField(
            model_name="discount",
            name="discount_type",
            field=models.CharField(
                choices=[
                    ("percent-off", "percent-off"),
                    ("dollars-off", "dollars-off"),
                    ("fixed-price", "fixed-price"),
                    ("linked-purchase", "linked-purchase"),
                ],
                max_length=30,
            ),
        ),
        migrations.AlterField(
            model_name="discount",
            name="redemption_type",
            field=models.CharField(
                choices=[
                    ("one-time", "one-time"),
                    ("one-time-per-user", "one-time-per-user"),
                    ("unlimited", "unlimited"),
                    ("linked-purchase", "linked-purchase"),
                ],
                max_length=30,
            ),
        ),
    ]
