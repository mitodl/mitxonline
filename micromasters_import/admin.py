"""micromasters_import admin"""
from django.contrib import admin
from micromasters_import.models import CourseId, ProgramId


class ProgramIdAdmin(admin.ModelAdmin):
    """Admin for ProgramId"""

    model = ProgramId
    list_display = ("program", "micromasters_id")


class CourseIdAdmin(admin.ModelAdmin):
    """Admin for CourseId"""

    model = CourseId
    list_display = ("course", "micromasters_id")


admin.site.register(CourseId, CourseIdAdmin)
admin.site.register(ProgramId, ProgramIdAdmin)
