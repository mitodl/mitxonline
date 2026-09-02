"""
Preview certificates that would still have no certificate_page_revision
after the automatic backfill in
courses/migrations/0104_certificate_page_revision_not_nullable.py runs.

Run this against a database snapshot BEFORE deploying that migration: it
applies the same "does this course/program have a live certificate page with
a saved revision" lookup the migration's backfill uses, and reports only the
certificates for which that lookup still comes up empty. Those need a human
to publish/fix the underlying CertificatePage - certificate pages are never
auto-created - before the migration can succeed in that environment (the
migration's AlterField will otherwise fail with a NOT NULL violation and
roll back).
"""

from django.core.management.base import BaseCommand

from courses.models import CourseRunCertificate, ProgramCertificate


class Command(BaseCommand):
    """Print a report of certificates the upcoming migration can't fix."""

    help = (
        "Preview which CourseRunCertificates/ProgramCertificates would still "
        "have no certificate_page_revision after the "
        "certificate_page_revision_not_nullable migration's automatic "
        "backfill runs - i.e. whose course/program has no live, revisioned "
        "certificate page."
    )

    def handle(self, *args, **options):  # noqa: ARG002
        course_run_certificates = [
            cert
            for cert in CourseRunCertificate.all_objects.filter(
                certificate_page_revision__isnull=True
            ).select_related("user", "course_run__course")
            if not self._resolvable(cert.course_run.course.certificate_page)
        ]
        program_certificates = [
            cert
            for cert in ProgramCertificate.all_objects.filter(
                certificate_page_revision__isnull=True
            ).select_related("user", "program")
            if not self._resolvable(cert.program.certificate_page)
        ]

        self.stdout.write(
            self.style.WARNING(
                "CourseRunCertificates the migration can't fix: "
                f"{len(course_run_certificates)}"
            )
        )
        self.stdout.write(
            self.style.WARNING(
                "ProgramCertificates the migration can't fix: "
                f"{len(program_certificates)}"
            )
        )

        self._print_items(
            "CourseRunCertificate",
            (
                f"id={cert.id} user={cert.user.edx_username} "
                f"course={cert.course_run.course.readable_id} "
                f"courserun={cert.course_run.courseware_id}"
                for cert in course_run_certificates
            ),
        )
        self._print_items(
            "ProgramCertificate",
            (
                f"id={cert.id} user={cert.user.edx_username} "
                f"program={cert.program.readable_id}"
                for cert in program_certificates
            ),
        )

    def _resolvable(self, certificate_page):
        """Would the migration's backfill find a revision to use here?"""
        return bool(certificate_page and certificate_page.get_latest_revision())

    def _print_items(self, label, lines):
        """Print a list of description lines under a label, if there are any."""
        printed_header = False
        for line in lines:
            if not printed_header:
                self.stdout.write(self.style.WARNING(f"{label} details:"))
                printed_header = True
            self.stdout.write(f"- {line}")
