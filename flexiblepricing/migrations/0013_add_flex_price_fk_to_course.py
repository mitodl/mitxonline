# Generated by Django 3.2.12 on 2022-05-09 19:25

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("courses", "0011_fix_default_enrollment_mode_for_existing_enrollments"),
        ("flexiblepricing", "0012_add_exchange_rate_description"),
    ]

    operations = [
        migrations.AddField(
            model_name="flexibleprice",
            name="course",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="courses.course",
            ),
        ),
    ]
