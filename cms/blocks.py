"""
Wagtail custom blocks for the CMS
"""

from django import forms
from django.apps import apps
from django.core.exceptions import ValidationError
from wagtail import blocks
from wagtail.images.blocks import ImageChooserBlock


class ResourceBlock(blocks.StructBlock):
    """
    A custom block for resource pages.
    """

    heading = blocks.CharBlock(max_length=100)
    detail = blocks.RichTextBlock()


class PriceBlock(blocks.StructBlock):
    """
    A custom block for price field.
    """

    text = blocks.CharBlock(
        max_length=150,
        help="Displayed over the product detail page under the price tile.",
    )
    link = blocks.URLBlock(
        required=False,
        help="Specify the URL to redirect the user for the product's price details page.",
    )


class FacultyBlock(blocks.StructBlock):
    """
    Block class that defines a faculty member
    """

    name = blocks.CharBlock(max_length=100, help_text="Name of the faculty member.")
    image = ImageChooserBlock(
        help_text="Profile image size must be at least 300x300 pixels."
    )
    description = blocks.RichTextBlock(
        help_text="A brief description about the faculty member."
    )


class CourseRunFieldBlock(blocks.FieldBlock):
    """
    Block class that allows selecting a course run
    """

    def get_courseruns(self):
        """Lazy evaluation of the queryset"""
        queryset = apps.get_model("courses", "CourseRun").objects.live()

        if self.parent_readable_id:
            queryset = queryset.filter(course__readable_id=self.parent_readable_id)
        return queryset.values_list("courseware_id", "courseware_id")

    def __init__(self, *args, required=True, help_text=None, **kwargs):
        self.parent_readable_id = None
        self.field = forms.ChoiceField(
            choices=self.get_courseruns, help_text=help_text, required=required
        )
        super().__init__(*args, **kwargs)


class CourseRunCertificateOverrides(blocks.StructBlock):
    """
    Block class that defines override values for a course run to be displayed on the certificate
    """

    readable_id = CourseRunFieldBlock(help_text="Course run to add the override for")
    CEUs = blocks.DecimalBlock(
        help_text="CEUs to override for this CourseRun, for display on the certificate"
    )


def validate_unique_readable_ids(value):
    """
    Validates that all of the course run override blocks in this stream field have
    unique readable IDs
    """
    # We want to validate the overall stream not underlying blocks individually
    if len(value) < 2:  # noqa: PLR2004
        return
    items = [
        stream_block.value.get("readable_id")
        for stream_block in value
        if stream_block.block_type == "course_run"
    ]
    if len(set(items)) != len(items):
        raise blocks.StreamBlockValidationError(
            non_block_errors=ValidationError(
                "Cannot have multiple overrides for the same course run.",
                code="invalid",
                params={"value": items},
            )
        )
