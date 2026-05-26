"""
Signals for mitxonline course certificates
"""

import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from courses.api import generate_multiple_programs_certificate
from courses.models import (
    CourseRunCertificate,
    Program,
    ProgramCertificate,
)
from hubspot_sync import tasks as hubspot_tasks
from hubspot_sync.api import (
    upsert_custom_properties as _upsert_custom_properties,
)


def upsert_custom_properties():
    """Proxy kept for backward compatibility with tests patching this symbol."""
    return _upsert_custom_properties()


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

    try:
        transaction.on_commit(
            lambda: hubspot_tasks.sync_course_run_certificate_with_hubspot.delay(
                instance.id
            )
        )
    except Exception:  # pylint: disable=broad-except
        logger = logging.getLogger(__name__)
        logger.exception("Error syncing HubSpot course run certificate")
        # avoid blocking certificate save flow


@receiver(
    post_save,
    sender=ProgramCertificate,
    dispatch_uid="programcertificate_post_save",
)
def handle_create_program_certificate(
    sender,  # pylint: disable=unused-argument  # noqa: ARG001
    instance,
    _created,  # pylint: disable=unused-argument
    **kwargs,  # pylint: disable=unused-argument  # noqa: ARG001
):
    """When a ProgramCertificate model is created."""
    try:
        transaction.on_commit(
            lambda: hubspot_tasks.sync_program_certificate_with_hubspot.delay(
                instance.id
            )
        )
    except Exception:  # pylint: disable=broad-except
        logger = logging.getLogger(__name__)
        logger.exception("Error syncing HubSpot program certificate")
        # avoid blocking certificate save flow
