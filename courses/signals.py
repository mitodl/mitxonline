"""
Signals for mitxonline course certificates
"""

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from courses.api import generate_multiple_programs_certificate
from courses.models import (
    Course,
    CourseRun,
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

    transaction.on_commit(
        lambda: hubspot_tasks.sync_course_run_certificate_with_hubspot.delay(
            instance.id
        )
    )


@receiver(
    post_save,
    sender=ProgramCertificate,
    dispatch_uid="programcertificate_post_save",
)
def handle_create_program_certificate(
    sender,  # pylint: disable=unused-argument  # noqa: ARG001
    instance,
    created=None,
    **kwargs,  # pylint: disable=unused-argument  # noqa: ARG001
):
    """When a ProgramCertificate model is created."""
    _ = created
    transaction.on_commit(
        lambda: hubspot_tasks.sync_program_certificate_with_hubspot.delay(instance.id)
    )


@receiver(post_save, sender=Course, dispatch_uid="course_post_save_fastly_purge")
def purge_fastly_cache_on_course_save(
    sender,  # noqa: ARG001
    instance,
    **kwargs,  # noqa: ARG001
):
    """
    Purges the Fastly surrogate key for a Course when it is saved,
    so that MIT Learn product pages reflecting this course are invalidated.
    """
    from cms.tasks import queue_fastly_surrogate_key_purge  # noqa: PLC0415

    surrogate_key = f"mitxonline:course:{instance.readable_id}"
    transaction.on_commit(lambda: queue_fastly_surrogate_key_purge.delay(surrogate_key))


@receiver(post_save, sender=CourseRun, dispatch_uid="courserun_post_save_fastly_purge")
def purge_fastly_cache_on_course_run_save(
    sender,  # noqa: ARG001
    instance,
    **kwargs,  # noqa: ARG001
):
    """
    Purges the Fastly surrogate key for the parent Course when a CourseRun is
    saved (e.g. enrollment mode changes), so that MIT Learn
    product pages are invalidated.
    """
    from cms.tasks import queue_fastly_surrogate_key_purge  # noqa: PLC0415

    surrogate_key = f"mitxonline:course:{instance.course.readable_id}"
    transaction.on_commit(lambda: queue_fastly_surrogate_key_purge.delay(surrogate_key))


@receiver(post_save, sender=Program, dispatch_uid="program_post_save_fastly_purge")
def purge_fastly_cache_on_program_save(
    sender,  # noqa: ARG001
    instance,
    **kwargs,  # noqa: ARG001
):
    """
    Purges the Fastly surrogate key for a Program when it is
    saved (e.g. program requirements, enrollment modes),
    so that MIT Learn product pages are invalidated.
    """
    from cms.tasks import queue_fastly_surrogate_key_purge  # noqa: PLC0415

    surrogate_key = f"mitxonline:program:{instance.readable_id}"
    transaction.on_commit(lambda: queue_fastly_surrogate_key_purge.delay(surrogate_key))
