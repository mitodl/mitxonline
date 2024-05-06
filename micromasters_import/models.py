"""MicroMasters import models"""

from django.db import models
from wagtail.models import Revision


class CourseId(models.Model):  # noqa: DJ008
    """
    Map primary keys from MicroMasters to MITx Online for courses
    """

    micromasters_id = models.IntegerField(
        unique=True,
        null=False,
        help_text="The primary key of the record in MicroMasters",
    )

    course = models.OneToOneField(
        "courses.Course", unique=True, null=False, on_delete=models.CASCADE
    )


class ProgramId(models.Model):  # noqa: DJ008
    """
    Map primary keys from MicroMasters to MITx Online for programs
    """

    micromasters_id = models.IntegerField(
        unique=True,
        null=False,
        help_text="The primary key of the program in MicroMasters",
    )

    program = models.OneToOneField(
        "courses.Program",
        unique=True,
        null=False,
        on_delete=models.CASCADE,
        help_text="The primary key of the program in MITxOnline",
    )

    program_certificate_revision = models.ForeignKey(
        Revision,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        help_text="Program certificate page revision ID in MITxOnline (Used for importing program certificates)",
    )


class ProgramTierId(models.Model):
    """
    Map primary keys from MicroMasters financial aid to MITx Online flexible price tier
    """

    micromasters_tier_program_id = models.IntegerField(
        unique=True,
        null=False,
        help_text="The primary key of Tier Program in MicroMasters",
    )

    flexible_price_tier = models.OneToOneField(
        "flexiblepricing.FlexiblePriceTier",
        unique=True,
        null=False,
        on_delete=models.CASCADE,
    )

    def __str__(self):
        return f"Mapping MicroMaster Tier Program ID - {self.micromasters_tier_program_id} to MITxOnline Flexible Price Tier ID - {self.flexible_price_tier.id}"


class CourseCertificateRevisionId(models.Model):
    """
        Maps Course to the 'Current' Certificate Page Revision ID from CMS
    It's used to facilitate the migration in raw query
    """

    course = models.OneToOneField(
        "courses.Course", unique=True, null=False, on_delete=models.CASCADE
    )

    certificate_page_revision = models.ForeignKey(
        Revision, null=True, on_delete=models.CASCADE
    )

    def __str__(self):
        return f"Mapping Course - {self.course.title} to Certificate Page Revision - {self.certificate_page_revision.content_object.title}"
