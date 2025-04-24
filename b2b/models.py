"""Models for B2B data."""

from django.db import models
from django.http import Http404
from django.utils.text import slugify
from wagtail.admin.panels import FieldPanel
from wagtail.fields import RichTextField
from wagtail.models import Page

from b2b.constants import ORG_INDEX_SLUG


class OrganizationObjectIndexPage(Page):
    """The index page for organizations - provides the root level folder."""

    parent_page_types = ["cms.HomePage"]
    subpage_types = ["b2b.OrganizationPage"]

    class Meta:
        """Meta options for the OrganizationIndexPage."""

        abstract = True

    @classmethod
    def can_create_at(cls, parent):
        """
        You can only create one of these pages under the home page.
        The parent is limited via the `parent_page_type` list.
        """
        return (
            super().can_create_at(parent)
            and not parent.get_children().type(cls).exists()
        )

    def serve(self, request, *args, **kwargs):  # noqa: ARG002
        """
        For index pages we raise a 404 because these pages do not have a template
        of their own and we do not expect a page to available at their slug.
        """
        raise Http404


class OrganizationIndexPage(OrganizationObjectIndexPage):
    """The index page for organizations - provides the root level folder."""

    slug = ORG_INDEX_SLUG


class OrganizationPage(Page):
    """Stores information about an organization we have a relationship with."""

    name = models.CharField(max_length=255, help_text="The name of the organization")
    description = RichTextField(
        blank=True, help_text="Any useful extra information about the organization"
    )
    logo = models.ImageField(
        upload_to="organization_logos",
        blank=True,
        help_text="The organization's logo. Will be displayed in the app in various places.",
    )

    content_panels = [
        FieldPanel("name"),
        FieldPanel("description"),
        FieldPanel("logo"),
    ]

    promote_panels = []

    def save(self, clean=True, user=None, log_action=False, **kwargs):  # noqa: FBT002
        """Save the page, and update the slug and title appropriately."""

        self.title = str(self.name)

        self.slug = slugify(f"org-{self.get_parent().id}")
        Page.save(self, clean=clean, user=user, log_action=log_action, **kwargs)
