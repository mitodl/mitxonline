"""
Report certificates that still have no certificate_page_revision after
running migrate_certificate_revisions --all-missing.

These are certificates whose course/program has no live certificate page at
all, or whose certificate page has never had a revision saved - neither of
which migrate_certificate_revisions can fix on its own, since certificate
pages are never auto-created. Each row here needs a human to publish/fix the
underlying CertificatePage.

This command is meant as the pre-deploy gate for making
certificate_page_revision non-nullable: it should report zero rows in an
environment before that environment's migration to add the NOT NULL
constraint is run.
"""

from django.core.management.base import BaseCommand

from courses.models import CourseRunCertificate, ProgramCertificate


class Command(BaseCommand):
    """Print a report of certificates with no certificate_page_revision."""

    help = (
        "Report CourseRunCertificates/ProgramCertificates that have no "
        "certificate_page_revision and cannot be backfilled because their "
        "course/program has no live, revisioned certificate page."
    )

    def handle(self, *args, **options):  # noqa: ARG002
        course_run_certificates = CourseRunCertificate.all_objects.filter(
            certificate_page_revision__isnull=True
        ).select_related("user", "course_run__course")
        program_certificates = ProgramCertificate.all_objects.filter(
            certificate_page_revision__isnull=True
        ).select_related("user", "program")

        self.stdout.write(
            self.style.WARNING(
                "CourseRunCertificates missing a revision: "
                f"{course_run_certificates.count()}"
            )
        )
        self.stdout.write(
            self.style.WARNING(
                "ProgramCertificates missing a revision: "
                f"{program_certificates.count()}"
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

    def _print_items(self, label, lines):
        """Print a list of description lines under a label, if there are any."""
        printed_header = False
        for line in lines:
            if not printed_header:
                self.stdout.write(self.style.WARNING(f"{label} details:"))
                printed_header = True
            self.stdout.write(f"- {line}")
