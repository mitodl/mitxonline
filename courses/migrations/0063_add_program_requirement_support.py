# Generated by Django for MITx Online

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("courses", "0062_update_courserun_name_unique"),
    ]

    operations = [
        migrations.AddField(
            model_name="programrequirement",
            name="required_program",
            field=models.ForeignKey(
                blank=True,
                help_text="Program that is required to be completed",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="required_by",
                to="courses.program",
            ),
        ),
        migrations.AlterField(
            model_name="programrequirement",
            name="node_type",
            field=models.CharField(
                choices=[
                    ("program_root", "Program Root"),
                    ("operator", "Operator"),
                    ("course", "Course"),
                    ("program", "Program"),
                ],
                max_length=12,
                null=True,
            ),
        ),
        migrations.RemoveConstraint(
            model_name="programrequirement",
            name="courses_programrequirement_node_check",
        ),
        migrations.AddConstraint(
            model_name="programrequirement",
            constraint=models.CheckConstraint(
                check=models.Q(
                    models.Q(
                        ("course__isnull", True),
                        ("depth", 1),
                        ("node_type", "program_root"),
                        ("operator__isnull", True),
                        ("operator_value__isnull", True),
                        ("required_program__isnull", True),
                    ),
                    models.Q(
                        ("course__isnull", True),
                        ("depth__gt", 1),
                        ("node_type", "operator"),
                        ("operator__isnull", False),
                        ("required_program__isnull", True),
                    ),
                    models.Q(
                        ("course__isnull", False),
                        ("depth__gt", 1),
                        ("node_type", "course"),
                        ("operator__isnull", True),
                        ("operator_value__isnull", True),
                        ("required_program__isnull", True),
                    ),
                    models.Q(
                        ("course__isnull", True),
                        ("depth__gt", 1),
                        ("node_type", "program"),
                        ("operator__isnull", True),
                        ("operator_value__isnull", True),
                        ("required_program__isnull", False),
                    ),
                    _connector="OR",
                ),
                name="courses_programrequirement_node_check",
            ),
        ),
        migrations.AlterIndexTogether(
            name="programrequirement",
            index_together={
                ("program", "course"),
                ("course", "program"),
                ("program", "required_program"),
                ("required_program", "program"),
            },
        ),
    ]
