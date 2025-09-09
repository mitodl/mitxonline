"""User admin"""

import json

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as ContribUserAdmin
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from django_object_actions import DjangoObjectActions, action
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
<div style="background-color: #dc3545; color: #fff; padding: 10px; font-size: 16px; border-radius: 5px; margin-bottom: 10px;">
   <strong>WARNING:</strong><br/>
   Changing this username will require you to apply the same change in edX immediately after.<br /><br>
   Do not make this change unless you can perform the same change to the edX username, or you have someone
   else lined up to do it.
</div>
<div style="background-color: #0088e2; color: #fff; padding: 10px; font-size: 16px; border-radius: 5px;">
   <strong>NOTE:</strong><br/>
   If the user has not been synced to openedx yet, you will need to set Desired Edx Username as well. <br/><br/>
   This is ultimately the source of truth on what value to start with when attempting to create the user.
</div>
"""


class OpenEdxUserInline(admin.StackedInline):
    """Admin view for OpenedxUser"""

    model = OpenEdxUser

    readonly_fields = (
        "has_been_synced",
        "platform",
        "has_sync_error",
        "pretty_sync_error_data",
    )

    exclude = ("sync_error_data",)

    @admin.display(description="Sync Error Data")
    def pretty_sync_error_data(self, instance):
        pretty_json = json.dumps(instance.sync_error_data, indent=4, sort_keys=True)
        return mark_safe(f"<pre>{escape(pretty_json)}</pre>")  # noqa: S308

    can_delete = False
    max_num = 1
    extra = 0

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "edx_username",
                    "desired_edx_username",
                    "has_been_synced",
                    "has_sync_error",
                    "pretty_sync_error_data",
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
class UserAdmin(
    DjangoObjectActions, ContribUserAdmin, HijackUserAdminMixin, TimestampedModelAdmin
):
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
        (_("Personal Info"), {"fields": ("name", "email", "global_id")}),
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
        "id",
        "global_id",
        "email",
        "name",
        "is_staff",
        "last_login",
    )
    list_filter = (
        "is_staff",
        "is_superuser",
        "is_active",
        "groups",
        ("global_id", admin.EmptyFieldListFilter),
    )
    search_fields = ("openedx_users__edx_username", "name", "email", "global_id")
    ordering = ("email",)
    readonly_fields = ("last_login", "hubspot_sync_datetime", "global_id")
    inlines = [
        OpenEdxUserInline,
        UserLegalAddressInline,
        UserProfileInline,
        UserContractPageInline,
    ]

    @action(label="Clear Sync Errors", description="Clear OpenedX errors and resync")
    def clear_sync_errors(self, request, obj):  # noqa: ARG002
        obj.openedx_users.update(has_sync_error=False, sync_error_data=None)

    change_actions = ["clear_sync_errors"]


@admin.register(BlockList)
class BlockListAdmin(admin.ModelAdmin):
    """Admin for BlockList"""

    model = BlockList
    list_display = ("hashed_email",)

    def has_add_permission(self, request):  # noqa: ARG002
        return False
