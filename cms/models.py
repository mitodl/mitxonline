"""CMS model definitions"""
from django.db import models
from wagtail.admin.edit_handlers import FieldPanel
from wagtail.core.fields import RichTextField
from wagtail.core.models import Page
from wagtail.images.models import Image
from wagtail.images.edit_handlers import ImageChooserPanel


class HomePage(Page):
    """
    Site home page
    """

    template = "home_page.html"

    hero = models.ForeignKey(
        Image,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Main image displayed at the top of the home page. (The recommended dimensions for hero image are "
        "1920x400)",
    )
    hero_title = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="The title text to display in the hero section of the home page.",
    )
    hero_subtitle = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="The subtitle text to display in the hero section of the home page.",
    )

    content_panels = Page.content_panels + [
        ImageChooserPanel("hero"),
        FieldPanel("hero_title"),
        FieldPanel("hero_subtitle"),
    ]
    parent_page_types = [Page]
    subpage_types = [
        "CoursePage",
    ]


class ProductPage(Page):
    """
    Abstract detail page for course runs and any other "product" that a user can enroll in
    """

    class Meta:
        abstract = True

    description = RichTextField(
        blank=True, help_text="The description shown on the product page"
    )
    feature_image = models.ForeignKey(
        Image,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Image that will be used where the course is featured or linked.",
    )

    template = "product_page.html"

    content_panels = Page.content_panels + [
        FieldPanel("description"),
        FieldPanel("feature_image"),
    ]
    parent_page_types = ["HomePage"]
    subpage_types = []


class CoursePage(ProductPage):
    """
    Detail page for courses
    """

    course = models.OneToOneField(
        "courses.Course", null=True, on_delete=models.SET_NULL, related_name="page"
    )

    content_panels = [FieldPanel("course")] + ProductPage.content_panels
