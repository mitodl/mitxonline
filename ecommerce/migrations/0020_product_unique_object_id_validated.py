# Generated by Django 3.2.14 on 2022-08-02 20:39

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ecommerce", "0019_db_protect_product"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="product",
            constraint=models.UniqueConstraint(
                condition=models.Q(("is_active", True)),
                fields=("object_id", "is_active"),
                name="unique_object_id_validated",
            ),
        ),
    ]
