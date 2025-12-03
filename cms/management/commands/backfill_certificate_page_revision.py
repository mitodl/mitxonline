import csv
import json
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

    def revision_has_same_signatories(self, certificate_revision, signatory_blocks):
        page_obj = certificate_revision.as_object()
        rev_signatory_ids = [child.value.id for child in page_obj.signatories]
        new_signatory_ids = [sp.id for _, sp in signatory_blocks]
        return rev_signatory_ids == new_signatory_ids

    def process_certificate_page_revision(self, row, row_num):
        certificate_page_id = row.get("certificate_page_id", "").strip()
        signatories_json = row.get("signatory_names", "").strip()

        if not certificate_page_id:
            self.stderr.write(
                self.style.ERROR(f"Row {row_num}: Missing certificate_page_id")
            )
            return

        if not signatories_json:
            self.stderr.write(
                self.style.ERROR(f"Row {row_num}: Missing signatory_names JSON array")
            )
            return

        try:
            # Example: a list of pairs, e.g. [["Name1", "Name2"], ["Name3", "Name4"]]
            signatory_pairs = json.loads(signatories_json)
        except Exception:  # noqa: BLE001
            self.stderr.write(
                self.style.ERROR(
                    f"Row {row_num}: signatory_names is not valid JSON: {signatories_json}"
                )
            )
            return

        # Load the CertificatePage
        certificate_page = CertificatePage.objects.get(id=certificate_page_id).specific

        # Copy the original live revision to restore later
        original_live_revision = certificate_page.get_latest_revision()

        backfill_created = False
        for index, signatory_names in enumerate(signatory_pairs, start=1):
            if not isinstance(signatory_names, list) or not signatory_names:
                self.stderr.write(
                    self.style.ERROR(
                        f"Row {row_num}: Pair #{index} must be a non-empty list of names: {signatory_names}"
                    )
                )
                continue

            signatory_pages = list(
                SignatoryPage.objects.filter(name__in=signatory_names)
            )
            found_names = {s.name for s in signatory_pages}
            missing = [n for n in signatory_names if n not in found_names]

            if missing:
                self.stderr.write(
                    self.style.WARNING(
                        f"Row {row_num} Pair {index}: Missing SignatoryPage(s): {missing}"
                    )
                )
                continue

            signatory_blocks = [
                ("signatory", signatory_page) for signatory_page in signatory_pages
            ]

            backfill_signatories = StreamValue(
                certificate_page.signatories.stream_block,
                signatory_blocks,
                is_lazy=False,
            )

            if any(
                self.revision_has_same_signatories(revision, signatory_blocks)
                for revision in certificate_page.revisions.all()
            ):
                self.stdout.write(
                    self.style.WARNING(
                        f"Row {row_num} Pair {index}: Identical revision already exists"
                    )
                )
                continue

            # Apply new signatories
            certificate_page.signatories = backfill_signatories

            # create the backfilled historical revision
            backfill_revision = certificate_page.save_revision(
                changed=True,
                log_action="wagtail.edit",
            )
            backfill_revision.publish()

            backfill_created = True
            self.stdout.write(
                self.style.SUCCESS(
                    f"Row {row_num} Pair {index}: Created revision {backfill_revision.id} for CertificatePage {certificate_page_id}"
                )
            )

        if backfill_created:
            # Restore original live revision
            restored_page = original_live_revision.as_object()
            restored_page.pk = certificate_page.pk
            restored_revision = restored_page.save_revision(
                changed=False,
                log_action="wagtail.revert",
            )
            restored_revision.publish()

            self.stdout.write(
                self.style.SUCCESS(
                    f"Row {row_num}: Restored original live revision {restored_revision.id} for CertificatePage {certificate_page_id}"
                )
            )
