"""Models for B2B data."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.http import Http404
from django.utils.text import slugify
from mitol.common.models import TimestampedModel
from mitol.common.utils import now_in_utc
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.fields import RichTextField
from wagtail.models import Page

from b2b.constants import CONTRACT_INTEGRATION_CHOICES, ORG_INDEX_SLUG
from b2b.tasks import queue_enrollment_code_check


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
    org_key = models.CharField(
        max_length=10,
        help_text="The short key used for the organization (for edX).",
        unique=True,
    )
    description = RichTextField(
        blank=True, help_text="Any useful extra information about the organization"
    )
    logo = models.ImageField(
        upload_to="organization_logos",
        blank=True,
        help_text="The organization's logo. Will be displayed in the app in various places.",
    )
    sso_organization_id = models.UUIDField(
        "Organization SSO ID",
        null=True,
        blank=True,
        help_text="The UUID for the organization in the SSO provider.",
    )

    content_panels = [
        FieldPanel("name"),
        FieldPanel("description"),
        FieldPanel("logo"),
        FieldPanel("sso_organization_id"),
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

    name = models.CharField(max_length=255, help_text="The name of the contract.")
    description = RichTextField(
        blank=True, help_text="Any useful extra information about the contract."
    )
    integration_type = models.CharField(
        max_length=255,
        choices=CONTRACT_INTEGRATION_CHOICES,
        help_text="The type of integration for this contract.",
    )
    organization = models.ForeignKey(
        OrganizationPage,
        on_delete=models.PROTECT,
        related_name="contracts",
        help_text="The organization this contract is with.",
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
    max_learners = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="The maximum number of learners allowed under this contract. (Set to zero or leave blank for unlimited.)",
    )
    enrollment_fixed_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="The fixed price for enrollment under this contract. (Set to zero or leave blank for free.)",
    )

    content_panels = [
        FieldPanel("name"),
        MultiFieldPanel(
            [
                FieldPanel("description"),
                FieldPanel("organization"),
            ],
            heading="Basic Information",
            icon="clipboard-list",
        ),
        MultiFieldPanel(
            [
                FieldPanel("integration_type"),
                FieldPanel("max_learners"),
                FieldPanel("enrollment_fixed_price"),
            ],
            heading="Learner Provisioning",
            icon="user",
        ),
        MultiFieldPanel(
            [
                FieldPanel("active"),
                FieldPanel("contract_start"),
                FieldPanel("contract_end"),
            ],
            heading="Availability",
            icon="calendar-alt",
        ),
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
        queue_enrollment_code_check.delay(self.id)

    def get_learners(self):
        """Get the learners associated with this organization."""

        return (
            get_user_model()
            .objects.filter(
                b2b_contracts=self,
            )
            .distinct()
        )

    def get_course_runs(self):
        """Get the runs associated with the contract."""

        from courses.models import CourseRun

        return (
            CourseRun.objects.prefetch_related("course").filter(b2b_contract=self).all()
        )

    def get_products(self):
        """Get the products associated with the contract."""

        from courses.models import CourseRun
        from ecommerce.models import Product

        content_type = ContentType.objects.get_for_model(CourseRun)

        return Product.objects.filter(
            is_active=True,
            content_type=content_type,
            object_id__in=[cr.id for cr in self.get_course_runs()],
        ).all()

    def get_discounts(self):
        """Get the discounts associated with the contract."""

        from ecommerce.models import Discount

        return Discount.objects.filter(products__product__in=self.get_products()).all()


class DiscountContractAttachmentRedemption(TimestampedModel):
    """Records when a discount was used to attach the user to a contract."""

    discount = models.ForeignKey(
        "ecommerce.Discount",
        on_delete=models.DO_NOTHING,
        help_text="The discount that was redemeed.",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.DO_NOTHING,
        help_text="The user that redeemed the discount.",
    )
    contract = models.ForeignKey(
        ContractPage,
        on_delete=models.DO_NOTHING,
        help_text="The contract that the user was attached to.",
    )
