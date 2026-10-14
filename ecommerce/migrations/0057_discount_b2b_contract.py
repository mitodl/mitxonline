import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("b2b", "0033_organizationpage_description_plain_text"),
        ("ecommerce", "0056_add_contract_fields_to_line_items"),
    ]

    operations = [
        migrations.AddField(
            model_name="discount",
            name="b2b_contract",
            field=models.ForeignKey(
                blank=True,
                help_text="The B2B contract this enrollment code belongs to, if it is one.",
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name="discounts",
                to="b2b.contractpage",
            ),
        ),
    ]
