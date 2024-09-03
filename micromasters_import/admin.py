"""micromasters_import admin"""

from django.contrib import admin

from micromasters_import.models import (
    CourseCertificateRevisionId,
    CourseId,
    ProgramId,
    ProgramTierId,
)


@admin.register(ProgramId)
class ProgramIdAdmin(admin.ModelAdmin):
    """Admin for ProgramId"""

    model = ProgramId
    list_display = ("program", "micromasters_id")
    raw_id_fields = ("program_certificate_revision",)


@admin.register(CourseId)
class CourseIdAdmin(admin.ModelAdmin):
    """Admin for CourseId"""

    model = CourseId
    list_display = ("course", "micromasters_id")


@admin.register(ProgramTierId)
class ProgramTieIdAdmin(admin.ModelAdmin):
    """Admin for ProgramTierId"""

    model = ProgramTierId
    list_display = ("micromasters_tier_program_id", "flexible_price_tier")


@admin.register(CourseCertificateRevisionId)
class CourseCertificateRevisionIdAdmin(admin.ModelAdmin):
    """Admin for CourseCertificateRevisionId"""

    model = CourseCertificateRevisionId
    list_display = ("course", "certificate_page_revision")
    raw_id_fields = ("certificate_page_revision",)


