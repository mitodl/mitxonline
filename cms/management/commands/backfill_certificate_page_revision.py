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

        certificate_page = CertificatePage.objects.get(id=certificate_page_id).specific

        if not signatories_list:
            self.stderr.write(
                self.style.WARNING(f"Row {row_num}: No signatories provided")
            )
            return

        signatory_blocks = [("signatory", signatory) for signatory in signatory_pages]
        backfill_signatories = StreamValue(
            certificate_page.signatories.stream_block,
            signatory_blocks,
            is_lazy=False,
        )

        # capture the current latest revision (before backfilling)
        original_live_revision = certificate_page.get_latest_revision()

        def revision_has_same_signatories(revision, new_signatories):
            rev_page = revision.as_object()
            rev_signatories = [
                child.value
                for child in rev_page.signatories
                if child.block.name == "signatory"
            ]
            new_signatory_values = [child.value for child in new_signatories]
            return rev_signatories == new_signatory_values

        # Skip if an identical revision exists
        if any(
            revision_has_same_signatories(r, backfill_signatories)
            for r in certificate_page.revisions.all()
        ):
            self.stdout.write(
                self.style.WARNING(
                    f"Row {row_num}: Backfill revision already exists for CertificatePage {certificate_page_id}"
                )
            )
            return

        certificate_page.signatories = backfill_signatories
        # create the backfilled historical revision
        backfill_revision = certificate_page.save_revision(
            changed=True, log_action="wagtail.edit"
        )
        backfill_revision.publish()

        self.stdout.write(
            self.style.SUCCESS(
                f"Row {row_num}: Created and published the backfill revision {backfill_revision.id} for CertificatePage {certificate_page_id}"
            )
        )

        # Restore previous live version
        restored_page = original_live_revision.as_object()
        restored_page.pk = certificate_page.pk
        restored_revision = restored_page.save_revision(
            changed=False, log_action="wagtail.revert"
        )
        restored_revision.publish()

        self.stdout.write(
            self.style.SUCCESS(
                f"Restored original revision {restored_revision.id} as latest for CertificatePage {certificate_page_id}"
            )
        )
