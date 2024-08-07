# Generated by Django 3.2.12 on 2022-03-15 13:49

import django_fsm
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("ecommerce", "0014_add_transaction_type_field"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReviewOrder",
            fields=[],
            options={
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=("ecommerce.order",),
        ),
        migrations.AlterField(
            model_name="order",
            name="state",
            field=django_fsm.FSMField(
                choices=[
                    ("pending", "Pending"),
                    ("fulfilled", "Fulfilled"),
                    ("canceled", "Canceled"),
                    ("refunded", "Refunded"),
                    ("declined", "Declined"),
                    ("errored", "Errored"),
                    ("review", "Review"),
                ],
                default="pending",
                max_length=50,
            ),
        ),
    ]
