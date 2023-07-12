"""
Signals for mitxonline course certificates
"""
from datetime import timedelta

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from mitol.common.utils import now_in_utc

from courses.models import (
    CourseRunCertificate,
    Program,
    CourseRun,
)
from courses.api import (
    generate_multiple_programs_certificate,
    generate_course_run_certificates_for_course,
)
from main import settings


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
        course = instance.course_run.course
        programs = list(
            Program.objects.filter(all_requirements__course=course).distinct()
        )
        if programs:
            transaction.on_commit(
                lambda: generate_multiple_programs_certificate(user, programs)
            )


@receiver(
    post_save,
    sender=CourseRun,
    dispatch_uid="courserun_post_save",
)
def handle_update_course_run(
    sender, instance, created, **kwargs
):  # pylint: disable=unused-argument
    """
    When a CourseRun model is updated, sync course run grades and generate missing certificates
    """
    if not created:
        now = now_in_utc()
        if (
            instance.certificate_available_date
            and instance.certificate_available_date <= now
        ):
            transaction.on_commit(
                lambda: generate_course_run_certificates_for_course(instance)
            )
