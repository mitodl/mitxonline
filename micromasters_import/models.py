"""MicroMasters import models"""
from django.db import models


class CourseId(models.Model):
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


class ProgramId(models.Model):
    """
    Map primary keys from MicroMasters to MITx Online for programs
    """

    micromasters_id = models.IntegerField(
        unique=True,
        null=False,
        help_text="The primary key of the record in MicroMasters",
    )

    program = models.OneToOneField(
        "courses.Program", unique=True, null=False, on_delete=models.CASCADE
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
