"""B2B model admin. Only for convenience; you should use the Wagtail interface instead."""

from django.contrib import admin

from b2b.models import (
    ContractPage,
    DiscountContractAttachmentRedemption,
    OrganizationPage,
)


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
        "contract_start",
        "contract_end",
        "max_learners",
        "enrollment_fixed_price",
    ]


@admin.register(OrganizationPage)
class OrganizationPageAdmin(ReadOnlyModelAdmin):
    """Admin for organization pages."""

    list_display = ["id", "slug", "name", "org_key"]
    fields = [
        "id",
        "slug",
        "name",
        "org_key",
        "description",
        "logo",
        "sso_organization_id",
    ]
