"""B2B model admin. Only for convenience; you should use the Wagtail interface instead."""

from django.contrib import admin

from b2b.models import (
    ContractPage,
    ContractProgramItem,
    DiscountContractAttachmentRedemption,
    OrganizationPage,
)
from courses.models import CourseRun


class ReadOnlyModelAdmin(admin.ModelAdmin):
    """Read-only admin for models."""

    def __init__(self, *args, **kwargs):
        """Set the readonly_fields to the fields if we can."""

        self.readonly_fields = self.fields or [
            field.name
            for field in self.model._meta.fields  # noqa: SLF001
        ]
        super().__init__(*args, **kwargs)

    def has_add_permission(self, request):  # noqa: ARG002
        """Disable create."""

        return False

    def has_delete_permission(self, request, obj=None):  # noqa: ARG002
        """Disable deletions."""

        return False


@admin.register(DiscountContractAttachmentRedemption)
class DiscountContractAttachmentRedemptionAdmin(ReadOnlyModelAdmin):
    """Admin for discount attachments."""

    list_display = ["user", "contract", "discount", "created_on"]
    date_hierarchy = "created_on"
    fields = ["user", "contract", "discount", "created_on"]
    readonly_fields = ["user", "contract", "discount", "created_on"]


class ContractPageProgramInline(admin.TabularInline):
    """Inline to display programs for contract pages."""

    model = ContractProgramItem
    extra = 0
    verbose_name = "Contract Program"
    verbose_name_plural = "Contract Programs"
    fields = ["program", "sort_order"]
    readonly_fields = ["program", "sort_order"]

    def has_add_permission(self, request, obj):  # noqa: ARG002
        """Turn off add permission. These admins are supposed to be read-only."""

        return False

    def has_delete_permission(self, request, obj):  # noqa: ARG002
        """Turn off delete permission. These admins are supposed to be read-only."""

        return False

    def has_change_permission(self, request, obj):  # noqa: ARG002
        """Turn off change permission. These admins are supposed to be read-only."""

        return False


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


@admin.register(ContractPage)
class ContractPageAdmin(ReadOnlyModelAdmin):
    """Admin for contract pages."""

    list_display = [
        "id",
        "slug",
        "title",
        "organization",
        "integration_type",
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
    inlines = [ContractPageCourseRunInline, ContractPageProgramInline]


@admin.register(OrganizationPage)
class OrganizationPageAdmin(ReadOnlyModelAdmin):
    """Admin for organization pages."""

    list_display = ["id", "slug", "name", "org_key", "sso_organization_id",]
    fields = [
        "id",
        "slug",
        "name",
        "org_key",
        "description",
        "logo",
        "sso_organization_id",
    ]
