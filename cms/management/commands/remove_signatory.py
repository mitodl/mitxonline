from django.core.management.base import BaseCommand
from wagtail.blocks import StreamValue

from cms.models import CertificatePage


class Command(BaseCommand):
    """Django management command to remove a signatory from all certificate pages.

    This command finds all certificate pages that contain a specific signatory
    and removes that signatory from their signatories field, creating new
    revisions and publishing the updated pages.
    """

    help = "Remove a signatory from all certificate pages and create new revisions"

    def add_arguments(self, parser):
        """Parses command line arguments."""
        parser.add_argument(
            "--signatory-id",
            type=int,
            help="ID of the signatory page to remove",
            required=True,
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show which certificate pages would be updated without making changes",
        )

    def handle(self, *args, **options):  # noqa: ARG002
        """Handles the command execution."""
        signatory_id = options["signatory_id"]
        dry_run = options["dry_run"]

        # Find all certificate pages that have this signatory
        certificate_pages = CertificatePage.objects.all()
        updated_count = 0

        if not certificate_pages:
            self.stdout.write(
                self.style.WARNING(
                    f"No certificate pages found with signatory ID {signatory_id}"
                )
            )
            return

        for cert_page in certificate_pages:
            signatory_blocks = list(cert_page.signatories)
            filtered_data = [
                {
                    "type": block.block_type,
                    "value": block.value.id,  # pass the page ID, NOT the whole page instance
                }
                for block in signatory_blocks
                if block.value.id != signatory_id
            ]

            if len(filtered_data) != len(signatory_blocks):
                if dry_run:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"[DRY RUN] Would remove signatory from certificate page {cert_page}"
                        )
                    )
                else:
                    cert_page.signatories = StreamValue(
                        cert_page.signatories.stream_block, filtered_data, is_lazy=True
                    )
                    cert_page.save_revision().publish()
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Successfully removed signatory from the certificate page {cert_page}"
                        )
                    )
                updated_count += 1

        if updated_count == 0:
            self.stdout.write(
                self.style.WARNING(
                    f"No certificate pages found with signatory ID {signatory_id}"
                )
            )
        else:
            action_text = (
                "[DRY RUN] Would remove" if dry_run else "Successfully removed"
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"{action_text} signatory from {updated_count} certificate pages"
                )
            )
