import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ecommerce", "0050_paid_amount_off_choices"),
    ]

    operations = [
        migrations.AddField(
            model_name="discountredemption",
            name="source_line",
            field=models.ForeignKey(
                blank=True,
                null=True,
                help_text="The prior purchase line that funds this redemption.",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="funded_redemptions",
                to="ecommerce.line",
            ),
        ),
    ]
