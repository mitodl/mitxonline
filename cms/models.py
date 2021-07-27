"""CMS model definitions"""
from django.conf import settings
from django.db import models
from wagtail.admin.edit_handlers import FieldPanel, StreamFieldPanel, PageChooserPanel
from wagtail.core.fields import RichTextField
from wagtail.core.models import Page
from wagtail.images.models import Image
from wagtail.images.edit_handlers import ImageChooserPanel
from wagtail.core.fields import StreamField

from cms.blocks import ResourceBlock


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
        help_text="Main image displayed at the top of the home page.",
    )

    content_panels = Page.content_panels + [
        FieldPanel("hero"),
    ]
    parent_page_types = [Page]
    subpage_types = [
        "CoursePage",
        "ResourcePage",
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


class ResourcePage(Page):
    """
    Basic resource page for all resource page.
    """

    template = "resource_page.html"
    parent_page_types = ["HomePage"]

    header_image = models.ForeignKey(
        Image,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Upload a header image that will render in the resource page.",
    )

    content = StreamField(
        [("content", ResourceBlock())],
        blank=False,
        help_text="Enter details of content.",
    )

    content_panels = Page.content_panels + [
        ImageChooserPanel("header_image"),
        StreamFieldPanel("content"),
    ]

    def get_context(self, request, *args, **kwargs):
        return {
            **super().get_context(request, *args, **kwargs),
            "site_name": settings.SITE_NAME,
        }
