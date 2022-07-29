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
