"""
Wagtail custom blocks for the CMS
"""
from wagtail.core import blocks
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
