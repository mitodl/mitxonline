"""Reads the signatories from a CSV file and populates the Signatory model in bulk."""

import csv
import logging
from pathlib import Path

import requests
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from wagtail.images.models import Image

from cms.models import SignatoryIndexPage, SignatoryPage

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Bulk populate signatories from a CSV file."""

    help = "Bulk populate signatories from a CSV file"

    def add_arguments(self, parser):
        """Parses command line arguments."""
        parser.add_argument(
            "--csv-file",
            type=str,
            help="Path to the CSV file containing signatory data",
            required=True,
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show which signatories would be created without making any changes",
        )

    def handle(self, *args, **options):  # noqa: ARG002
        """Handles the command execution."""
        csv_file_path = options["csv_file"]
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(self.style.WARNING("[DRY RUN] - No changes will be made"))
        try:
            with Path(csv_file_path).open("r", newline="", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)
                for row_num, row in enumerate(reader, start=2):  # Start at 2 for header
                    self.process_signatory(row, row_num, dry_run)

        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f"CSV file not found: {csv_file_path}"))
        except Exception as e:  # noqa: BLE001
            self.stdout.write(self.style.ERROR(f"Error processing CSV: {e!s}"))

    def fetch_or_create_signature_image(self, signatory_name, image_url):
        """Fetches an image from a URL and creates a Wagtail Image instance."""
        if not image_url:
            return None
        try:
            signature_image_title = f"{signatory_name} Signature"
            existing_image = Image.objects.filter(
                title__icontains=signature_image_title
            ).first()

            if existing_image:
                return existing_image
            else:
                response = requests.get(image_url, timeout=10)
                response.raise_for_status()

                # Extract filename from URL or create one
                filename = Path(image_url.split("?")[0]).name
                if not filename or "." not in filename:
                    filename = (
                        f"signatory_{signatory_name.replace(' ', '_').lower()}.jpg"
                    )

                # Create Wagtail Image instance
                image_file = ContentFile(response.content, name=filename)
                signature_image = Image(
                    title=f"{signatory_name} Signature", file=image_file
                )
                signature_image.save()
        except Exception as e:  # noqa: BLE001
            self.stdout.write(
                self.style.WARNING(
                    f"Could not download image for '{signatory_name}': {e!s}"
                )
            )
            return None
        else:
            return signature_image

    def process_signatory(self, row, row_num, dry_run):
        """Processes a single signatory row."""
        name = row.get("name", "").strip()
        signatory_title = row.get("signatory_title", "").strip()
        signatory_image_url = row.get("signatory_image_url", "").strip()

        if not name:
            self.stdout.write(
                self.style.WARNING(f"Row {row_num}: Skipping - no name provided")
            )
            return

        # Check for duplicates
        existing_signatory = SignatoryPage.objects.filter(name=name).first()

        try:
            if dry_run:
                if existing_signatory:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'[DRY RUN] Row {row_num}: Signatory already exists - would skip "{name}"'
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'[DRY RUN] Row {row_num}: Would create signatory "{name}"'
                        )
                    )
            else:
                signature_image = self.fetch_or_create_signature_image(
                    name, signatory_image_url
                )

                if existing_signatory:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Row {row_num}: Signatory already exists - skipping "{name}"'
                        )
                    )
                else:
                    # Create new signatory
                    # Download and create image if URL provided
                    signatory_index_page = SignatoryIndexPage.objects.first()
                    if not signatory_index_page:
                        raise ValidationError("No SignatoryIndexPage found in the CMS.")  # noqa: EM101, TRY301

                    signatory_page = SignatoryPage(
                        name=name,
                        title_1=signatory_title,
                        signature_image=signature_image,
                    )
                    signatory_index_page.add_child(instance=signatory_page)
                    signatory_page.save_revision().publish()

                    self.stdout.write(
                        self.style.SUCCESS(f'Row {row_num}: Created signatory "{name}"')
                    )

        except ValidationError as e:
            self.stdout.write(
                self.style.ERROR(f'Row {row_num}: Validation error for "{name}": {e!s}')
            )
        except Exception as e:  # noqa: BLE001
            self.stdout.write(
                self.style.ERROR(
                    f'Row {row_num}: Error processing signatory "{name}": {e!s}'
                )
            )
