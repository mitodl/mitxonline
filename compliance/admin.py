"""Admin for the compliance app"""

from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django_object_actions import DjangoObjectActions, action
from mitol.common.admin import TimestampedModelAdmin
from mitol.common.utils.datetime import now_in_utc

from compliance.models import ExportComplianceDecision, ExportComplianceLog
from main.utils import get_field_names


@admin.register(ExportComplianceLog)
class ExportComplianceLogAdmin(DjangoObjectActions, TimestampedModelAdmin):
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
    change_actions = ["mark_manually_approved"]

    def has_add_permission(self, request):  # noqa: ARG002
        return False

    def has_delete_permission(self, request, obj=None):  # noqa: ARG002
        return False

    @action(
        label="Mark Manually Approved",
        description="Mark this log as manually approved",
    )
    def mark_manually_approved(self, request, obj):
        """Approve this log, setting approved_by/approved_on to the current admin user and now."""
        obj.decision = ExportComplianceDecision.MANUALLY_APPROVED
        obj.approved_by = request.user
        obj.approved_on = now_in_utc()
        try:
            obj.full_clean()
        except ValidationError as exc:
            self.message_user(
                request,
                f"Could not approve log {obj.id}: {exc}",
                level=messages.ERROR,
            )
            return
        obj.save()
        self.message_user(request, f"Manually approved log {obj.id}.")
