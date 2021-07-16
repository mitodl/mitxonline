"""CMS model definitions"""
from django.db import models
from wagtail.admin.edit_handlers import FieldPanel
from wagtail.core.models import Page
from wagtail.images.models import Image


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
        "ProductPage",
    ]

    def get_context(self, request, *args, **kwargs):
        return {
            **super().get_context(request, *args, **kwargs),
            "hero": self.hero,
        }


class ProductPage(Page):
    """
    Detail page for course runs and any other "product" that a user can enroll in
    """

    template = "product_page.html"

    content_panels = Page.content_panels
    parent_page_types = ["HomePage"]
    subpage_types = []
