from django.db import migrations, models

INTERNAL = "internal"
UNLIMITED = "unlimited"


def flagged_rows_become_internal(apps, schema_editor):
    Discount = apps.get_model("ecommerce", "Discount")
    Discount.objects.filter(is_program_discount=True).update(redemption_type=INTERNAL)


def internal_rows_become_unlimited(apps, schema_editor):
    # Rows created after the forward step have the flag at its default (False),
    # and the previous release finds and prices these discounts by the flag.
    Discount = apps.get_model("ecommerce", "Discount")
    Discount.objects.filter(redemption_type=INTERNAL).update(
        redemption_type=UNLIMITED, is_program_discount=True
    )


class Migration(migrations.Migration):
    # The choices/help_text changes emit no SQL. ADD CONSTRAINT scans
    # ecommerce_discount (~600k rows) under the table lock, about a second,
    # the same trade-off 0054 made. A flagged row that is also automatic=True
    # aborts the whole (single-transaction) migration at the constraint, in
    # either operation order; that is intended, since it must not become an
    # auto-applied internal discount.

    dependencies = [
        ("ecommerce", "0054_paid_amount_off_discounts"),
    ]

    operations = [
        migrations.AlterField(
            model_name="discount",
            name="redemption_type",
            field=models.CharField(
                choices=[
                    ("one-time", "one-time"),
                    ("one-time-per-user", "one-time-per-user"),
                    ("unlimited", "unlimited"),
                    ("program-child-purchase", "program-child-purchase"),
                    ("internal", "internal"),
                ],
                help_text="'internal' discounts are attached by application code that has verified the learner's eligibility (e.g. verified program enrollment). Learners cannot redeem them and pricing does not re-check the product.",
                max_length=30,
            ),
        ),
        migrations.AlterField(
            model_name="discount",
            name="is_program_discount",
            field=models.BooleanField(
                blank=True,
                default=False,
                help_text="Deprecated and unused; superseded by redemption_type 'internal'.",
                null=True,
            ),
        ),
        migrations.AddConstraint(
            model_name="discount",
            constraint=models.CheckConstraint(
                condition=models.Q(("redemption_type", "internal"), _negated=True)
                | models.Q(("automatic", False)),
                name="internal_discount_never_automatic",
            ),
        ),
        migrations.RunPython(
            flagged_rows_become_internal, internal_rows_become_unlimited
        ),
    ]
