"""B2B model admin. Only for convenience; you should use the Wagtail interface instead."""

from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline
from django.db.models import Count

from b2b.models import (
    ContractPage,
    ContractProgramItem,
    DiscountContractAttachmentRedemption,
    OrganizationPage,
    UserOrganization,
)
from courses.models import CourseRun
from main.admin import DisplayOnlyAdminMixin, ReadOnlyModelAdmin


class UserOrganizationAdminInline(DisplayOnlyAdminMixin, admin.TabularInline):
    """Inline that filters to just show organization admins"""

    model = UserOrganization
    extra = 0
    verbose_name = "Organization Admin"
    list_display = [
        "user_email",
        "keep_until_seen",
        "is_manager",
    ]
    readonly_fields = [
        "user_email",
        "keep_until_seen",
        "is_manager",
    ]

    def get_queryset(self, request):
        """Filter the queryset to just users with Manager access."""

        return (
            super()
            .get_queryset(request)
            .prefetch_related("user")
            .filter(is_manager=True)
        )

    @admin.display(description="User Email")
    def user_email(self, obj):
        """Return the user's email address."""

        return obj.user.email


class ContractPagePossibleVariantInline(GenericTabularInline):
    """Inline for possible variants for a course"""

    from variants.models import SupportedVariant  # noqa: PLC0415

    model = SupportedVariant
    extra = 0


class OrganizationContractsInline(DisplayOnlyAdminMixin, admin.TabularInline):
    """Inline to display the contracts for the selected org"""

    model = ContractPage
    extra = 0
    fk_name = "organization"

    fields = [
        "title_linked",
        "slug",
        "membership_type",
        "max_learners",
        "active",
        "contract_start",
        "contract_end",
    ]
    readonly_fields = [
        "title_linked",
        "slug",
        "membership_type",
        "max_learners",
        "active",
        "contract_start",
        "contract_end",
    ]


class ContractPageProgramInline(DisplayOnlyAdminMixin, admin.TabularInline):
    """Inline to display programs for contract pages."""

    model = ContractProgramItem
    extra = 0
    verbose_name = "Contract Program"
    verbose_name_plural = "Contract Programs"
    fields = ["program", "sort_order"]
    readonly_fields = ["program", "sort_order"]


class ContractPageCourseRunInline(admin.TabularInline):
    """Inline to display course runs for contract pages."""

    model = CourseRun
    fk_name = "b2b_contract"
    extra = 0
    fields = [
        "courseware_id",
        "title",
    ]
    verbose_name = "Contract Course Run"
    verbose_name_plural = "Contract Course Runs"

    def has_add_permission(self, request, obj):  # noqa: ARG002
        """Turn off add permission. These admins are supposed to be read-only."""

        return False

    def has_delete_permission(self, request, obj):  # noqa: ARG002
        """Turn off delete permission. These admins are supposed to be read-only."""

        return False

    def has_change_permission(self, request, obj):  # noqa: ARG002
        """Turn off change permission. These admins are supposed to be read-only."""

        return False


@admin.register(DiscountContractAttachmentRedemption)
class DiscountContractAttachmentRedemptionAdmin(ReadOnlyModelAdmin):
    """Admin for discount attachments."""

    list_display = ["user", "contract", "discount", "created_on"]
    list_filter = [
        (
            "user",
            admin.RelatedOnlyFieldListFilter,
        ),
        (
            "contract",
            admin.RelatedOnlyFieldListFilter,
        ),
        (
            "user__user_organizations__organization",
            admin.RelatedOnlyFieldListFilter,
        ),
    ]
    date_hierarchy = "created_on"
    fields = ["user", "contract", "discount", "created_on"]
    readonly_fields = ["user", "contract", "discount", "created_on"]
    search_fields = [
        "user__email",
        "user__global_id",
        "contract__slug",
        "discount__discount_code",
    ]


@admin.register(ContractPage)
class ContractPageAdmin(ReadOnlyModelAdmin):
    """Admin for contract pages."""

    list_display = [
        "id",
        "slug",
        "title",
        "organization",
        "integration_type",
        "max_learners",
        "contract_start",
        "contract_end",
    ]
    list_filter = ["integration_type", "organization", "contract_start", "contract_end"]
    date_hierarchy = "contract_start"
    fields = [
        "id",
        "active",
        "slug",
        "organization",
        "title",
        "description",
        "integration_type",
        "membership_type",
        "contract_start",
        "contract_end",
        "max_learners",
        "enrollment_fixed_price",
    ]
    inlines = [
        ContractPageCourseRunInline,
        ContractPageProgramInline,
        ContractPagePossibleVariantInline,
    ]


@admin.register(OrganizationPage)
class OrganizationPageAdmin(ReadOnlyModelAdmin):
    """Admin for organization pages."""

    list_display = [
        "id",
        "slug",
        "name",
        "org_key",
        "sso_organization_id",
        "contract_count",
    ]
    fields = [
        "id",
        "slug",
        "name",
        "org_key",
        "description",
        "logo",
        "sso_organization_id",
    ]

    inlines = [
        UserOrganizationAdminInline,
        OrganizationContractsInline,
    ]

    def contract_count(self, obj):
        """Pull the contract count for the org."""

        return obj.contract_count if hasattr(obj, "contract_count") else "-"

    def get_queryset(self, request):
        """Add an annotation so we can have contract counts."""

        return super().get_queryset(request).annotate(contract_count=Count("contracts"))


@admin.register(UserOrganization)
class UserOrganizationAdmin(admin.ModelAdmin):
    """Admin for user organization memberships."""

    list_display = ["user", "organization", "is_manager", "keep_until_seen"]
    list_filter = ["is_manager", "keep_until_seen", "organization"]
    search_fields = ["user__email", "user__username", "organization__name"]
    fields = ["user", "organization", "is_manager", "keep_until_seen"]
