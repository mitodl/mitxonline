# Generated by Django 3.2.14 on 2022-07-28 01:34

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("courses", "0011_fix_default_enrollment_mode_for_existing_enrollments"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProgramId",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "micromasters_id",
                    models.IntegerField(
                        help_text="The primary key of the record in MicroMasters",
                        unique=True,
                    ),
                ),
                (
                    "program",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="courses.program",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="CourseId",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "micromasters_id",
                    models.IntegerField(
                        help_text="The primary key of the record in MicroMasters",
                        unique=True,
                    ),
                ),
                (
                    "course",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE, to="courses.course"
                    ),
                ),
            ],
        ),
    ]
