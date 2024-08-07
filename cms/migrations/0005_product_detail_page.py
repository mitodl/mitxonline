# Generated by Django 3.1.12 on 2021-08-05 08:31

import wagtail.blocks
import wagtail.fields
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("cms", "0004_add_hero_titles_image_chooser"),
    ]

    operations = [
        migrations.AddField(
            model_name="coursepage",
            name="about",
            field=wagtail.fields.RichTextField(
                blank=True, help_text="About this course details.", null=True
            ),
        ),
        migrations.AddField(
            model_name="coursepage",
            name="effort",
            field=models.CharField(
                blank=True,
                help_text="A short description indicating how much effort is required (e.g. 1-3 hours per week).",
                max_length=100,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="coursepage",
            name="length",
            field=models.CharField(
                blank=True,
                help_text="A short description indicating how long it takes to complete (e.g. '4 weeks').",
                max_length=50,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="coursepage",
            name="prerequisites",
            field=wagtail.fields.RichTextField(
                blank=True,
                help_text="A short description indicating prerequisites of this course.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="coursepage",
            name="price",
            field=wagtail.fields.StreamField(
                [
                    (
                        "price_details",
                        wagtail.blocks.StructBlock(
                            [
                                (
                                    "text",
                                    wagtail.blocks.CharBlock(
                                        help="Displayed over the product detail page under the price tile.",
                                        max_length=150,
                                    ),
                                ),
                                (
                                    "link",
                                    wagtail.blocks.URLBlock(
                                        help="Specify the URL to redirect the user for the product's price details page.",
                                        required=False,
                                    ),
                                ),
                            ]
                        ),
                    )
                ],
                blank=True,
                help_text="Specify the product price details.",
            ),
        ),
        migrations.AddField(
            model_name="coursepage",
            name="what_you_learn",
            field=wagtail.fields.RichTextField(
                blank=True, help_text="What you will learn from this course.", null=True
            ),
        ),
    ]
