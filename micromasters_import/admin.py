"""micromasters_import admin"""
from django.contrib import admin
from micromasters_import.models import (
    CourseId,
    CourseCertificateRevisionId,
    ProgramId,
    ProgramTierId,
)


class ProgramIdAdmin(admin.ModelAdmin):
    """Admin for ProgramId"""

    model = ProgramId
    list_display = ("program", "micromasters_id")


class CourseIdAdmin(admin.ModelAdmin):
    """Admin for CourseId"""

    model = CourseId
    list_display = ("course", "micromasters_id")


class ProgramTieIdAdmin(admin.ModelAdmin):
    """Admin for ProgramTierId"""

    model = ProgramTierId
    list_display = ("micromasters_tier_program_id", "flexible_price_tier")


class CourseCertificateRevisionIdAdmin(admin.ModelAdmin):
    """Admin for CourseCertificateRevisionId"""

    model = CourseCertificateRevisionId
    list_display = ("course", "certificate_page_revision")
    raw_id_fields = ("certificate_page_revision",)


admin.site.register(CourseId, CourseIdAdmin)
admin.site.register(ProgramId, ProgramIdAdmin)
admin.site.register(ProgramTierId, ProgramTieIdAdmin)
admin.site.register(CourseCertificateRevisionId, CourseCertificateRevisionIdAdmin)
