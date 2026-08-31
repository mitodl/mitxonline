import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    # A single plain migration on purpose. The choices changes emit no SQL, the
    # new column is nullable (instant), and the two ADD CONSTRAINT statements
    # scan ecommerce_discount (~600k rows) under the table lock — about a
    # second, accepted over the NOT VALID + VALIDATE dance for the sake of one
    # simple, atomic migration.

    dependencies = [
        ("ecommerce", "0051_refund_reason_choices_from_design"),
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
        migrations.AddField(
            model_name="discountredemption",
            name="source_line",
            field=models.ForeignKey(
                blank=True,
                null=True,
                help_text=(
                    "The prior purchase line that funds this linked-purchase "
                    "redemption."
                ),
                on_delete=django.db.models.deletion.PROTECT,
                related_name="funded_redemptions",
                to="ecommerce.line",
            ),
        ),
        migrations.AddConstraint(
            model_name="discount",
            constraint=models.CheckConstraint(
                condition=~models.Q(discount_type="linked-purchase")
                | (models.Q(redemption_type="linked-purchase") & models.Q(amount=0)),
                name="linked_purchase_discount_type_shape",
            ),
        ),
        migrations.AddConstraint(
            model_name="discount",
            constraint=models.CheckConstraint(
                condition=~models.Q(redemption_type="linked-purchase")
                | models.Q(automatic=True),
                name="linked_purchase_redemption_requires_automatic",
            ),
        ),
    ]
