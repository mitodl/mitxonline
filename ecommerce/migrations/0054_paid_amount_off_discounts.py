import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    # A single plain migration on purpose. The choices changes emit no SQL, the
    # new column is nullable (instant), and the two ADD CONSTRAINT statements
    # scan ecommerce_discount (~600k rows) under the table lock — about a
    # second, accepted over the NOT VALID + VALIDATE dance for the sake of one
    # simple, atomic migration.

    dependencies = [
        ("ecommerce", "0053_remove_order_reference_number_unique"),
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
                    ("paid-amount-off", "paid-amount-off"),
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
                    ("program-child-purchase", "program-child-purchase"),
                ],
                max_length=30,
            ),
        ),
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
        migrations.AddConstraint(
            model_name="discount",
            constraint=models.CheckConstraint(
                condition=~models.Q(discount_type="paid-amount-off")
                | (
                    models.Q(redemption_type="program-child-purchase")
                    & models.Q(amount=0)
                ),
                name="paid_amount_off_discount_shape",
            ),
        ),
        migrations.AddConstraint(
            model_name="discount",
            constraint=models.CheckConstraint(
                condition=~models.Q(redemption_type="program-child-purchase")
                | models.Q(automatic=True),
                name="program_child_purchase_requires_automatic",
            ),
        ),
    ]
