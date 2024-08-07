# Generated by Django 3.1.12 on 2021-08-11 12:16

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("courses", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="course",
            name="readable_id",
            field=models.CharField(
                max_length=255,
                unique=True,
                validators=[
                    django.core.validators.RegexValidator(
                        "^[\\w\\-+:\\.]+$",
                        "This field is used to produce URL paths. It must contain only characters that match this pattern: [\\w\\-+:\\.]",
                    )
                ],
            ),
        ),
        migrations.AlterField(
            model_name="program",
            name="readable_id",
            field=models.CharField(
                max_length=255,
                unique=True,
                validators=[
                    django.core.validators.RegexValidator(
                        "^[\\w\\-+:\\.]+$",
                        "This field is used to produce URL paths. It must contain only characters that match this pattern: [\\w\\-+:\\.]",
                    )
                ],
            ),
        ),
        migrations.AlterField(
            model_name="programrun",
            name="run_tag",
            field=models.CharField(
                max_length=10,
                validators=[
                    django.core.validators.RegexValidator(
                        "^[\\w\\-+:\\.]+$",
                        "This field is used to produce URL paths. It must contain only characters that match this pattern: [\\w\\-+:\\.]",
                    )
                ],
            ),
        ),
    ]
