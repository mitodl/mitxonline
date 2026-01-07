import time

from django.core.management import BaseCommand

from courses.api import create_verifiable_credential
from courses.models import CourseRun, CourseRunCertificate, Program, ProgramCertificate


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
            help="Comma-separated list of readable ids for the programs or course runs to backfill",
            required=True,
        )
        parser.add_argument(
            "-f",
            "--force",
            type=bool,
            help="If specified, will regenerate credentials even if they already exist",
            default=False,
        )
        parser.add_argument(
            "-s",
            "--sleep",
            type=float,
            help="If specified, sleeps this many seconds between processing each certificate to avoid overloading external services",
            default=0.0,
        )

    def generate_credential_for_certificate(self, certificate, *, force=False):
        """
        Generate a verifiable credential for a given certificate
        We may want to wrap this in a transaction in the future if force=True gets a lot of use
        """
        if not certificate.verifiable_credential or force:
            if certificate.verifiable_credential:
                self.stdout.write(
                    self.style.WARNING(
                        f"Deleting and regenerating verifiable credential for certificate {certificate}"
                    )
                )
                certificate.verifiable_credential.delete()
            create_verifiable_credential(certificate, raise_on_error=True)
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"Certificate {certificate} already has a verifiable credential; skipping."
                )
            )

    def handle(self, *args, **options):  # noqa: ARG002
        # These are either the readable IDs of a program or the IDs of course runs to process
        ids = options["ids"].split(",")
        force = options["force"]
        sleep = options["sleep"]
        certificates = []
        if options["type"] == "program":
            program_ids = Program.objects.filter(readable_id__in=ids).values_list(
                "id", flat=True
            )
            certificates = ProgramCertificate.objects.filter(id__in=program_ids)
        elif options["type"] == "course":
            course_run_ids = CourseRun.objects.filter(
                courseware_id__in=ids
            ).values_list("id", flat=True)
            certificates = CourseRunCertificate.objects.filter(
                course_run_id__in=course_run_ids
            )

        for cert in certificates:
            try:
                self.generate_credential_for_certificate(cert, force=force)
                self.stdout.write(
                    self.style.SUCCESS(f"Backfilled certificate for program {cert}")
                )
                time.sleep(sleep)
            except Exception:  # noqa: BLE001, PERF203
                self.stderr.write(
                    self.style.ERROR(
                        f"Failed to backfill certificate for program {cert}"
                    )
                )
