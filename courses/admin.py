"""
Admin site bindings for profiles
"""

from django.contrib import admin
from django.db import models
from django.forms import TextInput
from mitol.common.admin import TimestampedModelAdmin
from django.contrib.admin.decorators import display

from courses.models import (
    Course,
    CourseRun,
    CourseRunEnrollment,
    CourseRunEnrollmentAudit,
    CourseRunGrade,
    CourseRunGradeAudit,
    CourseTopic,
    BlockedCountry,
    Program,
    ProgramEnrollment,
    ProgramEnrollmentAudit,
    ProgramRun,
    PaidCourseRun,
)
from main.admin import AuditableModelAdmin
from main.utils import get_field_names


class ProgramAdmin(admin.ModelAdmin):
    """Admin for Program"""

    model = Program
    search_fields = ["title", "readable_id"]
    list_display = ("id", "title", "readable_id")
    list_filter = ["live"]


class ProgramRunAdmin(admin.ModelAdmin):
    """Admin for ProgramRun"""

    model = ProgramRun
    list_display = ("id", "program", "run_tag", "full_readable_id")
    list_filter = ["program"]
    raw_id_fields = ("program",)


class CourseAdmin(admin.ModelAdmin):
    """Admin for Course"""

    model = Course
    search_fields = ["title", "topics__name", "readable_id"]
    list_display = (
        "id",
        "title",
        "readable_id",
    )
    list_filter = ["live", "program", "topics"]
    raw_id_fields = ("program",)

    formfield_overrides = {
        models.CharField: {"widget": TextInput(attrs={"size": "80"})}
    }


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
    )
    list_filter = ["live", "course"]
    raw_id_fields = ("course",)

    formfield_overrides = {
        models.CharField: {"widget": TextInput(attrs={"size": "80"})}
    }


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

    def get_user_email(self, obj):
        """Returns the related User email"""
        return obj.user.email

    get_user_email.short_description = "User Email"
    get_user_email.admin_order_field = "user__email"

    def get_program_readable_id(self, obj):
        """Returns the related Program readable_id"""
        return obj.program.readable_id

    get_program_readable_id.short_description = "Program"
    get_program_readable_id.admin_order_field = "program__readable_id"


class ProgramEnrollmentAuditAdmin(TimestampedModelAdmin):
    """Admin for ProgramEnrollmentAudit"""

    model = ProgramEnrollmentAudit
    include_created_on_in_list = True
    list_display = ("id", "enrollment_id", "get_program_readable_id", "get_user")
    readonly_fields = get_field_names(ProgramEnrollmentAudit)

    def get_program_readable_id(self, obj):
        """Returns the related Program readable_id"""
        return obj.enrollment.program.readable_id

    get_program_readable_id.short_description = "Program"
    get_program_readable_id.admin_order_field = "enrollment__program__readable_id"

    def get_user(self, obj):
        """Returns the related User's email"""
        return obj.enrollment.user.email

    get_user.short_description = "User"
    get_user.admin_order_field = "enrollment__user__email"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class CourseRunEnrollmentAdmin(AuditableModelAdmin):
    """Admin for CourseRunEnrollment"""

    model = CourseRunEnrollment
    search_fields = [
        "user__email",
        "user__username",
        "run__courseware_id",
        "run__title",
    ]
    list_filter = ["active", "change_status", "edx_enrolled"]
    list_display = ("id", "get_user_email", "get_run_courseware_id", "change_status")
    raw_id_fields = (
        "user",
        "run",
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
        return qs.select_related("user", "run")

    def get_user_email(self, obj):
        """Returns the related User email"""
        return obj.user.email

    get_user_email.short_description = "User Email"
    get_user_email.admin_order_field = "user__email"

    def get_run_courseware_id(self, obj):
        """Returns the related CourseRun courseware_id"""
        return obj.run.courseware_id

    get_run_courseware_id.short_description = "Course Run"
    get_run_courseware_id.admin_order_field = "run__courseware_id"


class CourseRunEnrollmentAuditAdmin(TimestampedModelAdmin):
    """Admin for CourseRunEnrollmentAudit"""

    model = CourseRunEnrollmentAudit
    include_created_on_in_list = True
    list_display = ("id", "enrollment_id", "get_run_courseware_id", "get_user")
    readonly_fields = get_field_names(CourseRunEnrollmentAudit)

    def get_run_courseware_id(self, obj):
        """Returns the related CourseRun courseware_id"""
        return obj.enrollment.run.courseware_id

    get_run_courseware_id.short_description = "Course Run"
    get_run_courseware_id.admin_order_field = "enrollment__run__courseware_id"

    def get_user(self, obj):
        """Returns the related User's email"""
        return obj.enrollment.user.email

    get_user.short_description = "User"
    get_user.admin_order_field = "enrollment__user__email"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class CourseRunGradeAdmin(admin.ModelAdmin):
    """Admin for CourseRunGrade"""

    model = CourseRunGrade
    list_display = ["id", "get_user_email", "get_run_courseware_id", "grade"]
    list_filter = ["passed", "set_by_admin", "course_run__courseware_id"]
    raw_id_fields = ("user",)
    search_fields = ["user__email", "user__username"]

    def get_queryset(self, request):
        return self.model.objects.get_queryset().select_related("user", "course_run")

    def get_user_email(self, obj):
        """Returns the related User email"""
        return obj.user.email

    get_user_email.short_description = "User Email"
    get_user_email.admin_order_field = "user__email"

    def get_run_courseware_id(self, obj):
        """Returns the related CourseRun courseware_id"""
        return obj.course_run.courseware_id

    get_run_courseware_id.short_description = "Course Run"
    get_run_courseware_id.admin_order_field = "course_run__courseware_id"


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

    def get_user_email(self, obj):
        """Returns the related User email"""
        return obj.course_run_grade.user.email

    get_user_email.short_description = "User Email"
    get_user_email.admin_order_field = "course_run_grade__user__email"

    def get_run_courseware_id(self, obj):
        """Returns the related CourseRun courseware_id"""
        return obj.course_run_grade.course_run.courseware_id

    get_run_courseware_id.short_description = "Course Run"
    get_run_courseware_id.admin_order_field = (
        "course_run_grade__course_run__courseware_id"
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class CourseTopicAdmin(admin.ModelAdmin):
    """Admin for CourseTopic"""

    model = CourseTopic


class BlockedCountryAdmin(TimestampedModelAdmin):
    """Admin for BlockedCountry"""

    model = BlockedCountry
    search_fields = ["course__title", "course__readable_id", "country"]
    list_display = ("id", "course", "country")
    list_filter = ["course"]
    raw_id_fields = ("course",)


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


admin.site.register(Program, ProgramAdmin)
admin.site.register(ProgramRun, ProgramRunAdmin)
admin.site.register(Course, CourseAdmin)
admin.site.register(CourseRun, CourseRunAdmin)
admin.site.register(ProgramEnrollment, ProgramEnrollmentAdmin)
admin.site.register(ProgramEnrollmentAudit, ProgramEnrollmentAuditAdmin)
admin.site.register(CourseRunEnrollment, CourseRunEnrollmentAdmin)
admin.site.register(CourseRunEnrollmentAudit, CourseRunEnrollmentAuditAdmin)
admin.site.register(CourseRunGrade, CourseRunGradeAdmin)
admin.site.register(CourseRunGradeAudit, CourseRunGradeAuditAdmin)
admin.site.register(CourseTopic, CourseTopicAdmin)
admin.site.register(BlockedCountry, BlockedCountryAdmin)
admin.site.register(PaidCourseRun, PaidCourseRunAdmin)
