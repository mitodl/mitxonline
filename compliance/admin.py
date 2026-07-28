"""Admin for the compliance app"""

from django.contrib import admin
from mitol.common.admin import TimestampedModelAdmin

from compliance.models import ExportComplianceLog
from main.utils import get_field_names


@admin.register(ExportComplianceLog)
class ExportComplianceLogAdmin(TimestampedModelAdmin):
    """Read-only admin for ExportComplianceLog"""

    model = ExportComplianceLog
    include_created_on_in_list = True
    list_display = (
        "id",
        "user",
        "courseware_content_type",
        "courseware_object_id",
        "decision",
    )
    readonly_fields = get_field_names(ExportComplianceLog)

    def has_add_permission(self, request):  # noqa: ARG002
        return False

    def has_delete_permission(self, request, obj=None):  # noqa: ARG002
        return False
