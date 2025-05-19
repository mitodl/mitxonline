"""
Signals for mitxonline course certificates
"""

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from courses.api import generate_multiple_programs_certificate
from courses.models import (
    CourseRunCertificate,
    Program,
)
from hubspot_sync.task_helpers import sync_hubspot_user


@receiver(
    post_save,
    sender=CourseRunCertificate,
    dispatch_uid="courseruncertificate_post_save",
)
def handle_create_course_run_certificate(
    sender,  # pylint: disable=unused-argument  # noqa: ARG001
    instance,
    created,
    **kwargs,  # pylint: disable=unused-argument  # noqa: ARG001
):
    """
    When a CourseRunCertificate model is created.
    """
    if created:
        user = instance.user
        course = instance.course_run.course
        programs = list(
            Program.objects.filter(
                all_requirements__course=course, live=True
            ).distinct()
        )
        if programs:
            transaction.on_commit(
                lambda: generate_multiple_programs_certificate(user, programs)
            )
        sync_hubspot_user(instance.user)
