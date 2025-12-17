from django.core.management import BaseCommand

from courses.api import create_verifiable_credential
from courses.models import CourseRunCertificate, Program, ProgramCertificate


class Command(BaseCommand):
    """
    Backfill or repair verifiable credentials for program or course run certificates.
    """

    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument(
            "-t",
            "--type",
            choices=["program", "course"],
            help="Whether to backfill program certificates or course run certificates",
            required=True,
        )
        parser.add_argument(
            "-i",
            "--ids",
            type=str,
            help="The ids of the programs or course runs to backfill",
            required=True,
        )
        parser.add_argument(
            "-f",
            "--force",
            type=bool,
            help="If specified, will regenerate credentials even if they already exist",
            default=False,
        )

    def generate_credential_for_certificate(self, certificate, *, force=False):
        """Generate a verifiable credential for a given certificate"""
        if not certificate.verifiable_credential or force:
            create_verifiable_credential(certificate)
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"Certificate {certificate} already has a verifiable credential; skipping."
                )
            )

    def handle(self, *args, **options):  # noqa: ARG002
        """Handle command execution"""
        # These are either the readable IDs of a program or the IDs of course runs to process
        ids = options["ids"].split(",")
        force = options["force"]
        if options["type"] == "program":
            program_ids = Program.objects.filter(readable_id__in=ids).values_list(
                "id", flat=True
            )
            program_certificates = ProgramCertificate.objects.filter(id__in=program_ids)
            for cert in program_certificates:
                self.generate_credential_for_certificate(cert, force=force)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Backfilled certificates for program id={cert.id}"
                    )
                )
        elif options["type"] == "course":
            # Not sure if we'll look up by ID. That's a raw number; we might need to look up by something readable?
            course_run_certs = CourseRunCertificate.objects.filter(
                course_run_id__in=ids
            )
            for cert in course_run_certs:
                self.generate_credential_for_certificate(cert, force=force)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Backfilled certificates for course run id={cert.course_run_id}"
                    )
                )
