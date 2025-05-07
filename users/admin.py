"""User admin"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as ContribUserAdmin
from django.utils.translation import gettext_lazy as _
from hijack.contrib.admin import HijackUserAdminMixin
from mitol.common.admin import TimestampedModelAdmin

from openedx.models import OpenEdxUser
from users.models import BlockList, LegalAddress, User, UserProfile


class UserLegalAddressInline(admin.StackedInline):
    """Admin view for the legal address"""

    model = LegalAddress
    classes = ["collapse"]

    fieldsets = (
        (
            None,
            {
                "fields": (
                    ("first_name", "last_name"),
                    ("country", "state"),
                )
            },
        ),
    )

    def has_delete_permission(self, request, obj=None):  # noqa: ARG002
        return False


class UserProfileInline(admin.StackedInline):
    """Admin view for the profile"""

    model = UserProfile
    classes = ["collapse"]

    def has_delete_permission(self, request, obj=None):  # noqa: ARG002
        return True


_username_warning = """
<div style="background-color: #dc3545; color: #fff; padding: 10px; font-size: 16px; border-radius: 5px;">
   <strong>WARNING:</strong>
   Changing this username will require you to apply the same change in edX immediately after.<br /><br>
   Do not make this change unless you can perform the same change to the edX username, or you have someone
   else lined up to do it.
</div>
"""


class OpenEdxUserInline(admin.StackedInline):
    """Admin view for OpenedxUser"""

    model = OpenEdxUser

    readonly_fields = ("has_been_synced", "platform")

    can_delete = False
    max_num = 1
    extra = 0

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "edx_username",
                    "has_been_synced",
                ),
                "description": _username_warning,
            },
        ),
    )


class UserContractPageInline(admin.TabularInline):
    """Inline to allow modifying the contracts associated with a user"""

    model = User.b2b_contracts.through
    extra = 0


@admin.register(User)
class UserAdmin(ContribUserAdmin, HijackUserAdminMixin, TimestampedModelAdmin):
    """Admin views for user"""

    include_created_on_in_list = True
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "password",
                    "last_login",
                    "created_on",
                    "hubspot_sync_datetime",
                )
            },
        ),
        (_("Personal Info"), {"fields": ("name", "email")}),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
                "classes": ["collapse"],
            },
        ),
    )
    list_display = (
        "edx_username",
        "email",
        "name",
        "is_staff",
        "last_login",
    )
    list_filter = ("is_staff", "is_superuser", "is_active", "groups")
    search_fields = ("openedx_users__edx_username", "name", "email")
    ordering = ("email",)
    readonly_fields = ("last_login", "hubspot_sync_datetime")
    inlines = [
        OpenEdxUserInline,
        UserLegalAddressInline,
        UserProfileInline,
        UserContractPageInline,
    ]

    @admin.display(description="OpenedX Username")
    def edx_username(self, obj):
        return obj.edx_username


@admin.register(BlockList)
class BlockListAdmin(admin.ModelAdmin):
    """Admin for BlockList"""

    model = BlockList
    list_display = ("hashed_email",)

    def has_add_permission(self, request):  # noqa: ARG002
        return False
