"""
Admin site bindings for profiles
"""

from django.contrib import admin

from main.admin import ModelAdminRunActionsForAllMixin
from openedx.models import OpenEdxApiAuth, OpenEdxUser
from openedx.tasks import repair_faulty_openedx_users


@admin.register(OpenEdxUser)
class OpenEdxUserAdmin(ModelAdminRunActionsForAllMixin, admin.ModelAdmin):
    """Admin for OpenEdxUser"""

    model = OpenEdxUser
    search_fields = ["user__username", "user__email", "user__name", "platform"]
    list_display = ["id", "user", "has_been_synced", "platform"]
    list_filter = ["has_been_synced", "platform"]
    raw_id_fields = ["user"]
    actions = ["repair_all_faulty_openedx_users"]
    run_for_all_actions = ["repair_all_faulty_openedx_users"]
    readonly_fields = ["has_sync_error", "sync_error_data"]

    def get_queryset(self, request):
        """Overrides base queryset"""
        return super().get_queryset(request).select_related("user")

    @admin.action(description="Repair all faulty Open edX users")
    def repair_all_faulty_openedx_users(self, request, queryset):  # noqa: ARG002
        """Admin action to repair all faulty Open edX users"""
        repair_faulty_openedx_users.delay()
        self.message_user(
            request, "Repair all faulty Open edX users successfully requested."
        )


@admin.register(OpenEdxApiAuth)
class OpenEdxApiAuthAdmin(admin.ModelAdmin):
    """Admin for OpenEdxApiAuth"""

    model = OpenEdxApiAuth
    list_display = ["id", "user"]
    search_fields = ["user__username", "user__email", "user__name"]
    raw_id_fields = ["user"]

    def get_queryset(self, request):
        """Overrides base queryset"""
        return super().get_queryset(request).select_related("user")
