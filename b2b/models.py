"""Models for B2B data."""

from django.contrib.auth import get_user_model
from django.db import models
from django.http import Http404
from django.utils.text import slugify
from mitol.common.utils import now_in_utc
from wagtail.admin.panels import FieldPanel
from wagtail.fields import RichTextField
from wagtail.models import Page

from b2b.constants import CONTRACT_INTEGRATION_CHOICES, ORG_INDEX_SLUG


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

    parent_page_types = ["b2b.OrganizationIndexPage"]
    subpage_types = ["b2b.ContractPage"]

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

        self.slug = slugify(f"org-{self.name}")
        Page.save(self, clean=clean, user=user, log_action=log_action, **kwargs)

    def get_learners(self):
        """Get the learners associated with this organization."""

        return (
            get_user_model()
            .objects.filter(
                b2b_contracts__organization=self,
            )
            .distinct()
        )


class ContractPage(Page):
    """Stores information about a contract with an organization."""

    parent_page_types = ["b2b.OrganizationPage"]

    name = models.CharField(max_length=255, help_text="The name of the contract")
    description = RichTextField(
        blank=True, help_text="Any useful extra information about the contract"
    )
    integration_type = models.CharField(
        max_length=255,
        choices=CONTRACT_INTEGRATION_CHOICES,
        help_text="The type of integration for this contract",
    )
    organization = models.ForeignKey(
        OrganizationPage,
        on_delete=models.PROTECT,
        related_name="contracts",
        help_text="The organization this contract is with",
    )
    contract_start = models.DateField(
        blank=True,
        null=True,
        help_text="The start date of the contract.",
    )
    contract_end = models.DateField(
        blank=True,
        null=True,
        help_text="The end date of the contract.",
    )
    active = models.BooleanField(
        default=True,
        help_text="Whether this contract is active or not. Date rules still apply.",
    )

    content_panels = [
        FieldPanel("name"),
        FieldPanel("description"),
        FieldPanel("integration_type"),
        FieldPanel("organization"),
        FieldPanel("active"),
        FieldPanel("contract_start"),
        FieldPanel("contract_end"),
    ]

    promote_panels = []

    @property
    def is_active(self):
        """
        Check if the contract is active based on the dates and the active flag.
        """
        if self.contract_start and self.contract_start > now_in_utc():
            return False
        if self.contract_end and self.contract_end < now_in_utc():
            return False

        return self.active

    def __str__(self):
        """Return a string representation of the contract."""
        return f"{self.id} - {self.name} ({self.organization.name})"

    def save(self, clean=True, user=None, log_action=False, **kwargs):  # noqa: FBT002
        """Save the page, and update the slug and title appropriately."""

        self.title = str(self.name)

        self.slug = slugify(f"contract-{self.organization.id}-{self.id}")
        Page.save(self, clean=clean, user=user, log_action=log_action, **kwargs)

    def get_learners(self):
        """Get the learners associated with this organization."""

        return (
            get_user_model()
            .objects.filter(
                b2b_contracts=self,
            )
            .distinct()
        )
