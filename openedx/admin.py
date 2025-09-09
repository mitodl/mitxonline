"""
Admin site bindings for profiles
"""

from django.contrib import admin

from openedx.models import OpenEdxApiAuth, OpenEdxUser


@admin.register(OpenEdxUser)
class OpenEdxUserAdmin(admin.ModelAdmin):
    """Admin for OpenEdxUser"""

    model = OpenEdxUser
    search_fields = ["user__username", "user__email", "user__name", "platform"]
    list_display = ["id", "user", "has_been_synced", "platform"]
    list_filter = ["has_been_synced", "platform"]
    raw_id_fields = ["user"]
    readonly_fields = ["desired_edx_username"]

    def get_readonly_fields(self):
        fields = ["desired_edx_username"]

        if self.instance.has_been_synced:
            fields.append("desired_edx_username")
        else:
            fields.append("edx_username")

        return fields

    def get_queryset(self, request):
        """Overrides base queryset"""
        return super().get_queryset(request).select_related("user")


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
