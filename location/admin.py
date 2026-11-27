"""Admin for location data."""

from django.contrib import admin
from reversion.admin import VersionAdmin

from location import models


@admin.register(models.LocationFlag)
class LocationFlagAdmin(VersionAdmin):
    """Admin for LocationFlags"""

    model = models.LocationFlag
    search_fields = (
        "flag_type",
        "determination_rule",
    )
    list_display = (
        "id",
        "is_active",
        "flag_type",
        "determination_rule",
        "country_code",
    )
    list_filter = (
        "flag_type",
        "determination_rule",
    )

    def get_queryset(self, request):  # noqa: ARG002
        """Use the all_objects manager, so we can see deleted items."""

        return self.model.all_objects.get_queryset()
