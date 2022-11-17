"""
Signals for mitxonline course certificates
"""
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from courses.models import CourseRunCertificate, Program, ProgramRequirement, ProgramRequirementNodeType
from courses.utils import generate_program_certificate


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
        program = instance.course_run.course.program
        if program:
            transaction.on_commit(lambda: generate_program_certificate(user, program))


@receiver(
    post_save,
    sender=Program,
    dispatch_uid="program_create_requirements_root",
)
def handle_create_program_requirements_root(
    sender, instance, created, **kwargs
):  # pylint: disable=unused-argument
    """When a Program is created, create a ProgramRequirement root node for it"""
    if created and instance.requirements_root is None:
        ProgramRequirement.add_root(
            program=instance, node_type=ProgramRequirementNodeType.PROGRAM_ROOT.value
        )
