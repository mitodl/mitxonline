"""
Admin site bindings for profiles
"""

from django.contrib import admin
from django.contrib.admin.decorators import display
from django.db import models
from django.forms import TextInput
from django.urls import reverse
from mitol.common.admin import TimestampedModelAdmin

import cms.admin  # noqa: F401
from courses.api import downgrade_learner
from courses.forms import ProgramAdminForm
from courses.models import (
    BlockedCountry,
    Course,
    CourseRun,
    CourseRunCertificate,
    CourseRunEnrollment,
    CourseRunEnrollmentAudit,
    CourseRunGrade,
    CourseRunGradeAudit,
    Department,
    LearnerProgramRecordShare,
    PaidCourseRun,
    PaidProgram,
    PartnerSchool,
    Program,
    ProgramCertificate,
    ProgramCollectionItem,
    ProgramEnrollment,
    ProgramEnrollmentAudit,
    ProgramRun,
    RelatedProgram,
)
from main.admin import AuditableModelAdmin, ModelAdminRunActionsForAllMixin
from main.utils import get_field_names
from openedx.tasks import retry_failed_edx_enrollments


class ProgramContractPageInline(admin.TabularInline):
    """Inline for contract pages"""

    # Import here to avoid circular dependency at module load time
    from b2b.models import ContractProgramItem  # noqa: PLC0415

    model = ContractProgramItem
    extra = 0


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    """Admin for Program"""

    model = Program
    form = ProgramAdminForm
    search_fields = ["title", "readable_id", "program_type"]
    list_display = ("id", "title", "live", "readable_id", "program_type")
    list_filter = ["live", "program_type", "departments"]
    inlines = [ProgramContractPageInline]


@admin.register(ProgramRun)
class ProgramRunAdmin(admin.ModelAdmin):
    """Admin for ProgramRun"""

    model = ProgramRun
    list_display = ("id", "program", "run_tag", "readable_id")
    list_filter = ["program"]
    raw_id_fields = ("program",)


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    """Admin for Course"""

    model = Course
    search_fields = ["title", "departments__name", "readable_id"]
    ordering = ("id",)
    list_display = (
        "id",
        "title",
        "readable_id",
    )
    list_filter = ["live", "departments"]

    formfield_overrides = {
        models.CharField: {"widget": TextInput(attrs={"size": "80"})}
    }

    def get_readonly_fields(self, request, obj=None):  # noqa: ARG002
        """
        Adds `title` as readonly field while editing an existing object.
        """
        if getattr(obj, "page", None):
            return self.readonly_fields + ("title",)  # noqa: RUF005
        return self.readonly_fields

    def get_form(self, request, obj=None, change=False, **kwargs):  # noqa: FBT002
        """
        Adds help text for `title` field while editing an existing object.
        """
        if getattr(obj, "page", None):
            product_page_edit_url = (
                f"{reverse('wagtailadmin_home').rstrip('/')}/pages/{obj.page.id}/edit"
            )
            product_page_edit_link = (
                f"<a href={product_page_edit_url} target='_blank'>CMS Product Page</a>"
            )
            help_texts = {
                "title": f"You can update the course title using {product_page_edit_link}."
            }
            kwargs.update({"help_texts": help_texts})

        return super().get_form(request, obj=obj, change=change, **kwargs)


@admin.register(CourseRun)
class CourseRunAdmin(TimestampedModelAdmin):
    """Admin for CourseRun"""

    model = CourseRun
    search_fields = ["title", "courseware_id"]
    list_display = (
        "id",
        "title",
        "courseware_id",
        "run_tag",
        "start_date",
        "end_date",
        "enrollment_start",
        "upgrade_deadline",
    )
    list_filter = [
        "live",
        "is_source_run",
        "course",
        "b2b_contract",
    ]
    raw_id_fields = ("course",)

    formfield_overrides = {
        models.CharField: {"widget": TextInput(attrs={"size": "80"})},
        models.TextField: {"widget": TextInput(attrs={"size": "100"})},
    }


@admin.register(ProgramEnrollment)
class ProgramEnrollmentAdmin(AuditableModelAdmin):
    """Admin for ProgramEnrollment"""

    model = ProgramEnrollment
    search_fields = [
        "user__email",
        "user__username",
        "program__readable_id",
        "program__title",
    ]
    list_filter = ["active", "change_status"]
    list_display = ("id", "get_user_email", "get_program_readable_id", "change_status")
    raw_id_fields = (
        "user",
        "program",
    )

    def get_queryset(self, request):
        """
        Overrides base method. A filter was applied to the default queryset, so
        this method ensures that Django admin uses an unfiltered queryset.
        """
        qs = self.model.all_objects.get_queryset()
        # Code below was copied/pasted from the base method
        ordering = self.get_ordering(request)
        if ordering:
            qs = qs.order_by(*ordering)
        return qs.select_related("user", "program")

    @admin.display(
        description="User Email",
        ordering="user__email",
    )
    def get_user_email(self, obj):
        """Returns the related User email"""
        return obj.user.email

    @admin.display(
        description="Program",
        ordering="program__readable_id",
    )
    def get_program_readable_id(self, obj):
        """Returns the related Program readable_id"""
        return obj.program.readable_id


@admin.register(ProgramEnrollmentAudit)
class ProgramEnrollmentAuditAdmin(TimestampedModelAdmin):
    """Admin for ProgramEnrollmentAudit"""

    model = ProgramEnrollmentAudit
    include_created_on_in_list = True
    list_display = ("id", "enrollment_id", "get_program_readable_id", "get_user")
    readonly_fields = get_field_names(ProgramEnrollmentAudit)

    @admin.display(
        description="Program",
        ordering="enrollment__program__readable_id",
    )
    def get_program_readable_id(self, obj):
        """Returns the related Program readable_id"""
        return obj.enrollment.program.readable_id

    @admin.display(
        description="User",
        ordering="enrollment__user__email",
    )
    def get_user(self, obj):
        """Returns the related User's email"""
        return obj.enrollment.user.email

    def has_add_permission(self, request):  # noqa: ARG002
        return False

    def has_delete_permission(self, request, obj=None):  # noqa: ARG002
        return False


class CourseRunEnrollmentAuditInline(admin.TabularInline):
    """Inline editor for CourseRunEnrollmentAudit"""

    model = CourseRunEnrollmentAudit
    readonly_fields = [
        "enrollment_id",
        "created_on",
        "acting_user",
        "call_stack",
        "data_before",
        "data_after",
    ]
    min_num = 0
    extra = 0
    can_delete = False
    can_add = False

    def has_add_permission(self, request, obj=None):  # noqa: ARG002
        return False


@admin.register(CourseRunEnrollment)
class CourseRunEnrollmentAdmin(ModelAdminRunActionsForAllMixin, AuditableModelAdmin):
    """Admin for CourseRunEnrollment"""

    model = CourseRunEnrollment
    search_fields = [
        "user__email",
        "user__username",
        "run__courseware_id",
        "run__title",
    ]
    list_filter = ["active", "change_status", "edx_enrolled", "enrollment_mode"]
    list_display = (
        "id",
        "get_user_email",
        "get_run_courseware_id",
        "enrollment_mode",
        "change_status",
        "created_on",
    )
    raw_id_fields = (
        "user",
        "run",
    )
    inlines = [
        CourseRunEnrollmentAuditInline,
    ]
    actions = ["retry_all_failed_edx_enrollment", "downgrade_enrollment"]
    run_for_all_actions = ["retry_all_failed_edx_enrollment"]

    def get_queryset(self, request):
        """
        Overrides base method. A filter was applied to the default queryset, so
        this method ensures that Django admin uses an unfiltered queryset.
        """
        qs = self.model.all_objects.get_queryset()
        # Code below was copied/pasted from the base method
        ordering = self.get_ordering(request)
        if ordering:
            qs = qs.order_by(*ordering)
        return qs.select_related("user", "run")

    @admin.display(
        description="User Email",
        ordering="user__email",
    )
    def get_user_email(self, obj):
        """Returns the related User email"""
        return obj.user.email

    @admin.display(
        description="Course Run",
        ordering="run__courseware_id",
    )
    def get_run_courseware_id(self, obj):
        """Returns the related CourseRun courseware_id"""
        return obj.run.courseware_id

    @admin.action(description="Retry all failed Open edX enrollments")
    def retry_all_failed_edx_enrollment(self, request, queryset):  # noqa: ARG002
        """Admin action to retry all failed Open edX enrollments"""
        retry_failed_edx_enrollments.delay()
        self.message_user(
            request, "Retry all failed Open edX enrollments successfully requested."
        )

    @admin.action(description="Downgrade users enrollment")
    def downgrade_enrollment(self, request, queryset):
        """Admin action to change the status of users enrollment from verified to audit"""
        enrollment = queryset.first()
        _, enroll_success = downgrade_learner(enrollment)
        if not enroll_success:
            self.message_user(
                request,
                f"Failed to downgrade enrollment for user {enrollment.user.email}",
            )
        else:
            self.message_user(
                request,
                f"Successfully downgraded users enrollment from verified to audit: {enrollment.user.email}.",
            )


@admin.register(CourseRunEnrollmentAudit)
class CourseRunEnrollmentAuditAdmin(TimestampedModelAdmin):
    """Admin for CourseRunEnrollmentAudit"""

    model = CourseRunEnrollmentAudit
    include_created_on_in_list = True
    search_fields = [
        "enrollment__user__email",
        "enrollment__user__username",
        "enrollment__run__courseware_id",
    ]
    list_display = ("id", "enrollment_id", "get_run_courseware_id", "get_user")
    readonly_fields = get_field_names(CourseRunEnrollmentAudit)

    @admin.display(
        description="Course Run",
        ordering="enrollment__run__courseware_id",
    )
    def get_run_courseware_id(self, obj):
        """Returns the related CourseRun courseware_id"""
        return obj.enrollment.run.courseware_id

    @admin.display(
        description="User",
        ordering="enrollment__user__email",
    )
    def get_user(self, obj):
        """Returns the related User's email"""
        return obj.enrollment.user.email

    def has_add_permission(self, request):  # noqa: ARG002
        return False

    def has_delete_permission(self, request, obj=None):  # noqa: ARG002
        return False


@admin.register(CourseRunGrade)
class CourseRunGradeAdmin(admin.ModelAdmin):
    """Admin for CourseRunGrade"""

    model = CourseRunGrade
    list_display = [
        "id",
        "get_user_email",
        "get_user_username",
        "get_run_courseware_id",
        "grade",
    ]
    list_filter = ["passed", "set_by_admin", "course_run__courseware_id"]
    raw_id_fields = (
        "user",
        "course_run",
    )
    search_fields = ["user__email", "user__username"]

    def get_queryset(self, request):  # noqa: ARG002
        return self.model.objects.get_queryset().select_related("user", "course_run")

    @admin.display(
        description="User Email",
        ordering="user__email",
    )
    def get_user_email(self, obj):
        """Returns the related User email"""
        return obj.user.email

    @admin.display(
        description="Username",
        ordering="user__username",
    )
    def get_user_username(self, obj):
        """Returns the related User username"""
        return obj.user.edx_username

    @admin.display(
        description="Course Run",
        ordering="course_run__courseware_id",
    )
    def get_run_courseware_id(self, obj):
        """Returns the related CourseRun courseware_id"""
        return obj.course_run.courseware_id


@admin.register(CourseRunGradeAudit)
class CourseRunGradeAuditAdmin(TimestampedModelAdmin):
    """Admin for CourseRunGradeAudit"""

    model = CourseRunGradeAudit
    include_created_on_in_list = True
    list_display = (
        "id",
        "course_run_grade_id",
        "get_user_email",
        "get_run_courseware_id",
    )
    readonly_fields = get_field_names(CourseRunGradeAudit)

    @admin.display(
        description="User Email",
        ordering="course_run_grade__user__email",
    )
    def get_user_email(self, obj):
        """Returns the related User email"""
        return obj.course_run_grade.user.email

    @admin.display(
        description="Course Run",
        ordering="course_run_grade__course_run__courseware_id",
    )
    def get_run_courseware_id(self, obj):
        """Returns the related CourseRun courseware_id"""
        return obj.course_run_grade.course_run.courseware_id

    def has_add_permission(self, request):  # noqa: ARG002
        return False

    def has_delete_permission(self, request, obj=None):  # noqa: ARG002
        return False


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    """Admin for Department"""

    model = Department
    list_display = ("name", "slug")


@admin.register(BlockedCountry)
class BlockedCountryAdmin(TimestampedModelAdmin):
    """Admin for BlockedCountry"""

    model = BlockedCountry
    search_fields = ["course__title", "course__readable_id", "country"]
    list_display = ("id", "course", "country")
    list_filter = ["course"]
    raw_id_fields = ("course",)


@admin.register(PaidCourseRun)
class PaidCourseRunAdmin(TimestampedModelAdmin):
    """Admin for PaidCourseRun"""

    model = PaidCourseRun
    list_display = [
        "id",
        "get_user_email",
        "get_courseware_id",
        "get_order_id",
        "get_order_state",
    ]
    search_fields = ["course_run__courseware_id", "user__username", "user__email"]

    @display(description="User")
    def get_user_email(self, obj):
        return obj.user.email

    @display(description="Course Run")
    def get_courseware_id(self, obj):
        return obj.course_run.courseware_id

    @display(description="Order ID")
    def get_order_id(self, obj):
        return obj.order.id

    @display(description="Order State")
    def get_order_state(self, obj):
        return obj.order.state


@admin.register(PaidProgram)
class PaidProgramAdmin(TimestampedModelAdmin):
    """Admin for PaidProgram"""

    model = PaidProgram
    list_display = [
        "id",
        "get_user_email",
        "get_readable_id",
        "get_order_id",
        "get_order_state",
    ]
    search_fields = ["program__readable_id", "user__username", "user__email"]

    @display(description="User")
    def get_user_email(self, obj):
        return obj.user.email

    @display(description="Program")
    def get_readable_id(self, obj):
        return obj.program.readable_id

    @display(description="Order ID")
    def get_order_id(self, obj):
        return obj.order.id

    @display(description="Order State")
    def get_order_state(self, obj):
        return obj.order.state


@admin.register(CourseRunCertificate)
class CourseRunCertificateAdmin(TimestampedModelAdmin):
    """Admin for CourseRunCertificate"""

    model = CourseRunCertificate
    include_timestamps_in_list = True
    list_display = [
        "uuid",
        "user",
        "course_run",
        "get_certificate_page_title",
        "get_revoked_state",
    ]
    search_fields = [
        "course_run__courseware_id",
        "course_run__title",
        "user__username",
        "user__email",
    ]
    list_filter = ["is_revoked", "course_run__course"]
    raw_id_fields = ("user", "course_run", "verifiable_credential")
    autocomplete_fields = ("certificate_page_revision",)

    def get_readonly_fields(self, request, obj=None):
        """Make course_run and certificate_page_revision read-only when editing"""
        return list(super().get_readonly_fields(request, obj))

    @admin.display(
        description="Certificate Page",
    )
    def get_certificate_page_title(self, obj):
        """Returns the certificate page title from the revision"""
        if obj.certificate_page_revision:
            try:
                page = obj.certificate_page_revision.as_object()
                if hasattr(page, "title"):
                    return page.title
                return str(page)
            except (AttributeError, ValueError, TypeError):
                return f"Revision {obj.certificate_page_revision.id}"
        return "No certificate page"

    @admin.display(
        description="Active",
        boolean=True,
    )
    def get_revoked_state(self, obj):
        """Return the revoked state"""
        return obj.is_revoked is not True

    def get_queryset(self, request):  # noqa: ARG002
        return self.model.all_objects.get_queryset().select_related(
            "user", "course_run"
        )


@admin.register(ProgramCertificate)
class ProgramCertificateAdmin(TimestampedModelAdmin):
    """Admin for ProgramCertificate"""

    model = ProgramCertificate
    include_timestamps_in_list = True
    list_display = [
        "uuid",
        "user",
        "program",
        "get_revoked_state",
    ]
    search_fields = [
        "program__readable_id",
        "program__title",
        "user__username",
        "user__email",
    ]
    list_filter = ["program__title", "is_revoked"]
    raw_id_fields = ("user", "verifiable_credential")

    @admin.display(
        description="Active",
        boolean=True,
    )
    def get_revoked_state(self, obj):
        """Return the revoked state"""
        return obj.is_revoked is not True

    def get_queryset(self, request):  # noqa: ARG002
        return self.model.all_objects.get_queryset().select_related("user", "program")


@admin.register(PartnerSchool)
class PartnerSchoolAdmin(TimestampedModelAdmin):
    """Admin for PartnerSchool"""

    model = PartnerSchool
    list_display = ["name", "email"]
    search_fields = ["name", "email"]


@admin.register(LearnerProgramRecordShare)
class LearnerProgramRecordShareAdmin(TimestampedModelAdmin):
    """Admin for LearnerProgramRecordShare"""

    model = LearnerProgramRecordShare
    list_display = ["share_uuid", "user", "partner_school", "is_active"]
    search_fields = ["share_uuid"]


@admin.register(RelatedProgram)
class RelatedProgramAdmin(admin.ModelAdmin):
    """Admin for Program"""

    model = RelatedProgram
    list_display = ("id", "first_program", "second_program")
    list_filter = ["first_program", "second_program"]


@admin.register(ProgramCollectionItem)
class ProgramCollectionItemAdmin(admin.ModelAdmin):
    """Admin for ProgramCollectionItem"""

    model = ProgramCollectionItem
    list_display = ("id", "collection", "program", "sort_order")
    list_filter = ["collection"]
    ordering = ("collection", "sort_order")
