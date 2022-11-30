"""
Signals for mitxonline course certificates
"""
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from courses.models import (
    CourseRunCertificate,
    ProgramRequirement,
    ProgramRequirementNodeType,
)
from courses.utils import generate_multiple_programs_certificate


@receiver(
    post_save,
    sender=CourseRunCertificate,
    dispatch_uid="courseruncertificate_post_save",
)
def handle_create_course_run_certificate(
    sender, instance, created, **kwargs
):  # pylint: disable=unused-argument
    """
    When a CourseRunCertificate model is created.
    """
    if created:
        user = instance.user
        program_requirements = (
            ProgramRequirement.objects.filter(
                node_type=ProgramRequirementNodeType.COURSE,
                course=instance.course_run.course,
            )
            .order_by("program_id")
            .distinct("program_id")
        )
        programs = [
            program_requirement.program for program_requirement in program_requirements
        ]
        if programs:
            transaction.on_commit(
                lambda: generate_multiple_programs_certificate(user, programs)
            )
