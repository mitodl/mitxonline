import csv
from pathlib import Path

from django.core.management.base import BaseCommand
from wagtail.blocks import StreamValue

from cms.models import CertificatePage, SignatoryPage


class Command(BaseCommand):
    """Django management command to Wagtail CertificatePage revisions using a CSV file"""

    help = "Create backfilled revisions for CertificatePage objects using CSV input"

    def add_arguments(self, parser):
        """Parses command line arguments."""
        parser.add_argument(
            "--csv-file",
            type=str,
            help="Path to the CSV file containing signatory and certificate page information",
            required=True,
        )

    def handle(self, *args, **options):  # noqa: ARG002
        """Handles the command execution."""
        csv_file_path = options["csv_file"]

        try:
            with Path(csv_file_path).open("r", newline="", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)
                for row_num, row in enumerate(reader, start=2):  # Start at 2 for header
                    self.process_certificate_page_revision(row, row_num)

        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f"CSV file not found: {csv_file_path}"))
        except Exception as e:  # noqa: BLE001
            self.stdout.write(self.style.ERROR(f"Error processing CSV: {e!s}"))

    def process_certificate_page_revision(self, row, row_num):
        certificate_page_id = row.get("certificate_page_id", "").strip()
        signatories = row.get("signatory_names", "").strip()
        signatories_list = [
            name.strip() for name in signatories.split(",") if name.strip()
        ]
        signatory_pages = list(SignatoryPage.objects.filter(name__in=signatories_list))

        if not certificate_page_id:
            self.stderr.write(
                self.style.ERROR(f"Row {row_num}: Missing certificate_page_id")
            )
            return

        # Look up the page
        try:
            certificate_page = CertificatePage.objects.get(id=certificate_page_id)
        except CertificatePage.DoesNotExist:
            self.stderr.write(
                self.style.ERROR(
                    f"Row {row_num}: No CertificatePage with ID {certificate_page_id}"
                )
            )
            return

        if not signatories_list:
            self.stderr.write(
                self.style.WARNING(f"Row {row_num}: No signatories provided")
            )
            return

        certificate_page_for_revision = (
            certificate_page.get_latest_revision().as_object()
        )

        signatory_blocks = [
            {
                "type": "signatory",
                "value": signatory.id,
            }
            for signatory in signatory_pages
        ]

        certificate_page_for_revision.signatories = StreamValue(
            certificate_page_for_revision.signatories.stream_block,
            signatory_blocks,
            is_lazy=True,
        )

        revision = certificate_page_for_revision.save_revision()

        self.stdout.write(
            self.style.SUCCESS(
                f"Row {row_num}: Created revision {revision.id} for CertificatePage {certificate_page_id}"
            )
        )
