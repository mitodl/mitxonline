"""B2B model admin. Only for convenience; you should use the Wagtail interface instead."""

from django.contrib import admin

from b2b.models import (
    ContractPage,
    DiscountContractAttachmentRedemption,
    OrganizationPage,
)


@admin.register(DiscountContractAttachmentRedemption)
class DiscountContractAttachmentRedemptionAdmin(admin.ModelAdmin):
    """Admin for discount attachments."""

    list_display = ["user", "contract", "discount", "created_on"]
    date_hierarchy = "created_on"
    fields = ["user", "contract", "discount", "created_on"]
    readonly_fields = ["user", "contract", "discount", "created_on"]

    def has_add_permission(self, request):  # noqa: ARG002
        """Disable create."""

        return False

    def has_delete_permission(self, request, obj=None):  # noqa: ARG002
        """Disable deletions."""

        return False


admin.site.register(OrganizationPage)
admin.site.register(ContractPage)
