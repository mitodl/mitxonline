"""Models for B2B data."""

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.http import Http404
from django.utils.text import slugify
from mitol.common.models import TimestampedModel
from mitol.common.utils import now_in_utc
from requests.exceptions import HTTPError
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.fields import RichTextField
from wagtail.models import Page

from b2b.constants import (
    CONTRACT_MEMBERSHIP_AUTOS,
    CONTRACT_MEMBERSHIP_CHOICES,
    CONTRACT_MEMBERSHIP_MANAGED,
    CONTRACT_MEMBERSHIP_TYPE_CHOICES,
    ORG_INDEX_SLUG,
)
from b2b.exceptions import TargetCourseRunExistsError
from b2b.tasks import queue_enrollment_code_check

log = logging.getLogger(__name__)


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
        max_length=30,
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
        FieldPanel("org_key"),
        FieldPanel("logo"),
        FieldPanel("sso_organization_id"),
    ]

    # Use default promote_panels from Page to allow manual slug editing

    def save(self, clean=True, user=None, log_action=False, **kwargs):  # noqa: FBT002
        """Save the page, and update the slug and title appropriately."""

        self.title = str(self.name)

        if not self.slug:
            self.slug = slugify(f"org-{self.name}")
        Page.save(self, clean=clean, user=user, log_action=log_action, **kwargs)

    def get_learners(self):
        """Get the learners associated with this organization."""

        return (
            get_user_model()
            .objects.filter(
                b2b_organizations=self,
            )
            .distinct()
        )

    def attach_user(self, user):
        """
        Attach the given user to the org in Keycloak.

        Args:
        - user (User): the user to add to the org
        Returns:
        - bool: success flag
        """

        from b2b.api import add_user_org_membership

        try:
            return add_user_org_membership(self, user)
        except HTTPError:
            log.exception(
                "Got HTTP error attempting to attach %s to org %s, skipping", user, self
            )
            return False

    def add_user_contracts(self, user):
        """
        Add contracts that the user should get automatically to the user.

        Args:
        - user (User): the user to add contracts to
        Returns:
        - int: number of contracts added
        """

        contracts_qs = self.contracts.filter(
            integration_type__in=CONTRACT_MEMBERSHIP_AUTOS, active=True
        )

        for contract in contracts_qs.all():
            user.b2b_contracts.add(contract)

        return contracts_qs.count()

    def remove_user_contracts(self, user):
        """
        Remove managed contracts from the given user.

        Args:
        - user (User): the user to remove contracts from
        Returns:
        - int: number of contracts removed
        """

        return user.b2b_contracts.through.objects.filter(
            user_id=user.id,
            contractpage_id__in=self.contracts.filter(
                integration_type__in=CONTRACT_MEMBERSHIP_AUTOS
            ).values_list("id", flat=True)
        ).delete()

    def __str__(self):
        """Return a reasonable representation of the org as a string."""

        return f"{self.name} <{self.org_key}>"

    class Meta:
        """Meta options for the OrganizationPage."""

        verbose_name = "Organization"
        verbose_name_plural = "Organizations"
        constraints = [
            models.UniqueConstraint(
                fields=["sso_organization_id"], name="unique_sso_organization_id"
            )
        ]


class ContractPage(Page):
    """Stores information about a contract with an organization."""

    parent_page_types = ["b2b.OrganizationPage"]

    name = models.CharField(max_length=255, help_text="The name of the contract.")
    description = RichTextField(
        blank=True, help_text="Any useful extra information about the contract."
    )
    integration_type = models.CharField(
        max_length=255,
        choices=CONTRACT_MEMBERSHIP_CHOICES,
        help_text="The type of integration for this contract.",
    )
    # This doesn't have a choices setting because you can't re-use a constant.
    #
    membership_type = models.CharField(
        max_length=255,
        choices=CONTRACT_MEMBERSHIP_TYPE_CHOICES,
        help_text="The method to use to manage membership in the contract.",
        default=CONTRACT_MEMBERSHIP_MANAGED,
    )
    organization = models.ForeignKey(
        OrganizationPage,
        on_delete=models.PROTECT,
        related_name="contracts",
        help_text="The organization that owns this contract.",
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
    programs = models.ManyToManyField(
        "courses.Program",
        help_text="The programs associated with this contract.",
        related_name="contracts",
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
                FieldPanel("membership_type"),
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
        self.slug = slugify(f"contract-{self.organization.id}-{self.title}")

        # This should be removed once we're done migrating orgs into Keycloak.
        # The integration type field should also be removed at that time.
        self.membership_type = self.integration_type

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

    def is_full(self):
        """Determine if the contract is full or not."""

        return (
            self.get_learners().count() >= self.max_learners
            if self.max_learners
            else False
        )

    def is_overfull(self):
        """Determine if the contract is overcommitted."""

        return (
            self.get_learners().count() > self.max_learners
            if self.max_learners
            else False
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

    def add_program_courses(self, program):
        """
        Add a program, and then queue adding all its courses.

        Args:
        - program (courses.Program): the program to add

        Returns:
        - tuple, courses created and skipped
        """

        from b2b.api import create_contract_run

        managed = 0
        skipped = 0

        # Clear any cached properties to ensure fresh data
        if hasattr(program, "_courses_with_requirements_data"):
            delattr(program, "_courses_with_requirements_data")

        for course in program.courses_qset.filter(
            models.Q(courseruns__is_source_run=True)
            | models.Q(courseruns__run_tag="SOURCE")
        ).all():
            try:
                create_contract_run(self, course)
                managed += 1
            except TargetCourseRunExistsError:  # noqa: PERF203
                skipped += 1

        self.programs.add(program)

        return (managed, skipped)

    class Meta:
        """Meta options for the ContractPage."""

        verbose_name = "Contract"
        verbose_name_plural = "Contracts"


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


class UserOrganization(models.Model):
    """The user's organizations memberships."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="user_organizations",
    )
    organization = models.ForeignKey(
        "b2b.OrganizationPage",
        on_delete=models.CASCADE,
        related_name="organization_users",
    )
    keep_until_seen = models.BooleanField(
        default=False,
        help_text="If True, the user will be kept in the organization until the organization is seen in their SSO data.",
    )

    class Meta:
        unique_together = ("user", "organization")

    def __str__(self):
        """Return a reasonable representation of the object as a string."""

        return f"UserOrganization: {self.user} in {self.organization}"
