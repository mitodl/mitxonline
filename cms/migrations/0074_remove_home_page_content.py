import django.db.models.deletion
import modelcluster.fields
import wagtail.fields
from django.db import migrations, models

REMOVED_HOME_PAGE_FIELDS = [
    "hero",
    "hero_title",
    "hero_subtitle",
    "product_section_title",
    "video_component_title",
    "video_component_description",
    "video_url",
]


def delete_home_page_references(apps, schema_editor):
    """
    Delete reference-index rows recorded from the removed home page fields.

    Wagtail's "Usage" views resolve each row's field on the model and raise
    FieldDoesNotExist for a field that is gone, and these rows are only
    rebuilt when the home page is saved again.
    """
    ContentType = apps.get_model("contenttypes", "ContentType")
    ReferenceIndex = apps.get_model("wagtailcore", "ReferenceIndex")

    home_page_type = ContentType.objects.filter(app_label="cms", model="homepage")
    stale_ids = [
        ref_id
        for ref_id, model_path in ReferenceIndex.objects.filter(
            content_type__in=home_page_type
        ).values_list("id", "model_path")
        if model_path.split(".")[0] in [*REMOVED_HOME_PAGE_FIELDS, "featured_products"]
    ]
    ReferenceIndex.objects.filter(id__in=stale_ids).delete()


# Without the FK constraints, deleting a page or image can leave these columns
# pointing at nothing, and reversing this migration re-adds the constraints,
# which fails on such rows.
CLEAR_DANGLING_REFERENCES = """
UPDATE cms_homepage SET hero_id = NULL
    WHERE hero_id NOT IN (SELECT id FROM wagtailimages_image);
DELETE FROM cms_homeproductlink
    WHERE page_id NOT IN (SELECT page_ptr_id FROM cms_homepage)
    OR course_product_page_id NOT IN (SELECT id FROM wagtailcore_page);
"""


class Migration(migrations.Migration):
    dependencies = [
        ("cms", "0073_update_what_you_learn_help_text"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("wagtailcore", "0078_referenceindex"),
        ("wagtailimages", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(delete_home_page_references, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="coursepage",
            name="description",
            field=wagtail.fields.RichTextField(
                help_text="The description shown on the product page."
            ),
        ),
        migrations.AlterField(
            model_name="programpage",
            name="description",
            field=wagtail.fields.RichTextField(
                blank=True,
                help_text="The description shown on the product page.",
                null=True,
            ),
        ),
        migrations.SeparateDatabaseAndState(
            # The previous release still uses these while pods roll: Wagtail
            # loads the home page row on every page it serves, and creating or
            # deleting a page touches cms_homeproductlink. The columns and table
            # stay until a later migration drops them.
            database_operations=[
                # Django no longer knows about these columns, so deleting the
                # image or page one points at would not clear it, and the FK
                # would block the delete. Without the constraints, a test-DB
                # flush can also truncate the referenced tables.
                migrations.AlterField(
                    model_name="homepage",
                    name="hero",
                    field=models.ForeignKey(
                        null=True,
                        blank=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="+",
                        to="wagtailimages.image",
                        db_constraint=False,
                    ),
                ),
                migrations.AlterField(
                    model_name="homeproductlink",
                    name="page",
                    field=modelcluster.fields.ParentalKey(
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="featured_products",
                        to="cms.homepage",
                        db_constraint=False,
                    ),
                ),
                migrations.AlterField(
                    model_name="homeproductlink",
                    name="course_product_page",
                    field=models.ForeignKey(
                        null=True,
                        blank=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="+",
                        to="wagtailcore.page",
                        db_constraint=False,
                    ),
                ),
            ],
            state_operations=[
                migrations.DeleteModel(name="HomeProductLink"),
                *[
                    migrations.RemoveField(model_name="homepage", name=name)
                    for name in REMOVED_HOME_PAGE_FIELDS
                ],
            ],
        ),
        # Runs only on reverse, before the constraints above are re-added.
        migrations.RunSQL(migrations.RunSQL.noop, CLEAR_DANGLING_REFERENCES),
    ]
