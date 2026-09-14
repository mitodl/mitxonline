"""Admin for the compliance app"""

from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django_object_actions import DjangoObjectActions, action
from mitol.common.admin import TimestampedModelAdmin
from mitol.common.utils.datetime import now_in_utc

from compliance.models import ExportComplianceDecision, ExportComplianceLog
from main.utils import get_field_names


class ExportComplianceDecisionFilter(admin.SimpleListFilter):
    """Filter ExportComplianceLog by decision, with human-readable labels"""

    title = "decision"
    parameter_name = "decision"

    def lookups(self, request, model_admin):  # noqa: ARG002
        return ExportComplianceDecision.choices

    def queryset(self, request, queryset):  # noqa: ARG002
        value = self.value()
        if value:
            return queryset.filter(decision=value)
        return queryset


class ExportComplianceAcceptedFilter(admin.SimpleListFilter):
    """Filter ExportComplianceLog by whether the decision is an accepted one"""

    title = "accepted"
    parameter_name = "accepted"

    def lookups(self, request, model_admin):  # noqa: ARG002
        return (
            ("yes", "Yes"),
            ("no", "No"),
        )

    def queryset(self, request, queryset):  # noqa: ARG002
        value = self.value()
        if value == "yes":
            return queryset.filter(decision__in=ExportComplianceLog.ACCEPTED_DECISIONS)
        if value == "no":
            return queryset.exclude(decision__in=ExportComplianceLog.ACCEPTED_DECISIONS)
        return queryset


class ExportComplianceManuallyApprovedFilter(admin.SimpleListFilter):
    """Filter ExportComplianceLog by whether it has a manual approver set"""

    title = "manually approved"
    parameter_name = "manually_approved"

    def lookups(self, request, model_admin):  # noqa: ARG002
        return (
            ("yes", "Yes"),
            ("no", "No"),
        )

    def queryset(self, request, queryset):  # noqa: ARG002
        value = self.value()
        if value == "yes":
            return queryset.filter(approved_by__isnull=False)
        if value == "no":
            return queryset.filter(approved_by__isnull=True)
        return queryset


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
    list_filter = (
        ExportComplianceDecisionFilter,
        "courseware_content_type",
        ExportComplianceAcceptedFilter,
        ExportComplianceManuallyApprovedFilter,
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
