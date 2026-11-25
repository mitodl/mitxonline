import time

from django.core.management import BaseCommand, CommandError

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
        )
        parser.add_argument(
            "-i",
            "--ids",
            type=str,
            default="",
            help="Comma-separated list of readable ids for the programs or course runs to backfill",
        )
        parser.add_argument(
            "-f",
            "--force",
            action="store_true",
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
        parser.add_argument(
            "-e",
            "--execute",
            action="store_true",
            help="If specified, actually performs the backfill; otherwise, just simulates the process",
            default=False,
        )
        parser.add_argument(
            "-u",
            "--uuid",
            type=str,
            default=None,
            help="UUID for a certificate to generate a verifiable credential for",
        )

    def generate_credential_for_certificate(self, certificate, *, force=False):
        """
        Generate a verifiable credential for a given certificate.

        With force=True an existing credential is replaced, but only once the new one has been signed.
        A certificate whose page isn't set up to provision credentials is skipped and keeps what it has.
        """
        has_credential = bool(certificate.verifiable_credential)
        if has_credential and not force:
            self.stdout.write(
                self.style.WARNING(
                    f"Certificate {certificate} already has a verifiable credential; skipping."
                )
            )
            return

        if has_credential:
            self.stdout.write(
                self.style.WARNING(
                    f"Attempting to replace verifiable credential for certificate {certificate}"
                )
            )
        credential = create_verifiable_credential(
            certificate, raise_on_error=True, replace_existing=force
        )
        if not credential:
            self.stdout.write(
                self.style.WARNING(
                    f"Certificate {certificate} skipped: its certificate page isn't set up to provision "
                    "verifiable credentials. Any existing credential was left in place."
                )
            )
            return
        self.stdout.write(self.style.SUCCESS(f"Backfilled certificate {certificate}"))

    def validate_selection(self, ids, certificate_uuid, courseware_type):
        """Fail if the options do not select anything to backfill"""
        if certificate_uuid:
            return
        if not ids:
            msg = "You must provide either --ids or --uuid to backfill certificates."
            raise CommandError(msg)
        if not courseware_type:
            msg = "You must provide --type (program or course) with --ids."
            raise CommandError(msg)

    def handle(self, *args, **options):  # noqa: ARG002
        # These are either the readable IDs of a program or the IDs of course runs to process
        ids = [i.strip() for i in options["ids"].split(",") if i.strip()]
        force = options["force"]
        sleep = options["sleep"]
        execute = options["execute"]
        certificate_uuid = options["uuid"]
        courseware_type = options["type"]
        self.validate_selection(ids, certificate_uuid, courseware_type)

        certificates = []
        if certificate_uuid:
            certificate = ProgramCertificate.objects.filter(
                uuid=certificate_uuid
            ).first()
            if not certificate:
                certificate = CourseRunCertificate.objects.filter(
                    uuid=certificate_uuid
                ).first()
            if not certificate:
                self.stderr.write(
                    self.style.ERROR(
                        f"No certificate found with UUID {certificate_uuid}."
                    )
                )
                return
            certificates = [certificate]
        elif courseware_type == "program":
            program_ids = Program.objects.filter(readable_id__in=ids).values_list(
                "id", flat=True
            )
            certificates = ProgramCertificate.objects.filter(program_id__in=program_ids)
        elif courseware_type == "course":
            course_run_ids = CourseRun.objects.filter(
                courseware_id__in=ids
            ).values_list("id", flat=True)
            certificates = CourseRunCertificate.objects.filter(
                course_run_id__in=course_run_ids
            )

        for cert in certificates:
            try:
                if execute:
                    self.generate_credential_for_certificate(cert, force=force)
                else:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"DRY RUN -- Would backfill certificate {cert}"
                        )
                    )
                time.sleep(sleep)
            except Exception:  # noqa: BLE001, PERF203
                self.stderr.write(
                    self.style.ERROR(f"Failed to backfill certificate {cert}")
                )
