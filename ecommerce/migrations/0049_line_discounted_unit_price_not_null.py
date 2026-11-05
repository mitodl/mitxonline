from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ecommerce", "0048_backfill_line_discounted_unit_price"),
    ]

    operations = [
        migrations.AlterField(
            model_name="line",
            name="discounted_unit_price",
            field=models.DecimalField(
                decimal_places=5,
                help_text="Post-discount price of one unit, recorded when the order was priced.",
                max_digits=20,
            ),
        ),
    ]
