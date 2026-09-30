"""
Signals for mitxonline course certificates
"""

from django.conf import settings
from django.db import transaction
from django.db.models.signals import m2m_changed, post_save
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
    transaction.on_commit(
        lambda: queue_fastly_surrogate_key_purge.delay(
            surrogate_key, settings.MIT_LEARN_FASTLY_SERVICE_ID
        )
    )


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
    transaction.on_commit(
        lambda: queue_fastly_surrogate_key_purge.delay(
            surrogate_key, settings.MIT_LEARN_FASTLY_SERVICE_ID
        )
    )


@receiver(
    m2m_changed,
    sender=CourseRun.b2b_contracts.through,
    dispatch_uid="courserun_b2b_contracts_changed",
)
def validate_course_run_b2b_contracts(
    sender,  # noqa: ARG001
    instance,
    action,
    pk_set,
    *,
    reverse,
    **kwargs,  # noqa: ARG001
):
    """
    Re-check the B2B contract group uniqueness rules whenever
    ``CourseRun.b2b_contracts`` gains associations.

    ``run.b2b_contracts.add(...)`` and ``contract.course_runs.add(...)`` bypass
    ``CourseRun.save()``/``clean()``, so this is where the rules that used to be
    database UniqueConstraints on ``b2b_contract`` get enforced for M2M writes.
    See ``CourseRun.validate_b2b_contract_group_uniqueness``.
    """
    if action != "pre_add":
        return

    if reverse:
        # instance is a ContractPage, pk_set holds the CourseRun ids being added
        for run in CourseRun.all_objects.filter(pk__in=pk_set or []):
            run.validate_b2b_contract_group_uniqueness(
                {*run.contract_group_ids, instance.pk}
            )
        return

    # instance is a CourseRun, pk_set holds the ContractPage ids being added
    instance.validate_b2b_contract_group_uniqueness(
        {*instance.contract_group_ids, *(pk_set or [])}
    )


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
    transaction.on_commit(
        lambda: queue_fastly_surrogate_key_purge.delay(
            surrogate_key, settings.MIT_LEARN_FASTLY_SERVICE_ID
        )
    )
