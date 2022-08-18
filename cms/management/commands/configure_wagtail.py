"""Ensures that all appropriate changes have been made to Wagtail that will make the site navigable."""
from django.core.management.base import BaseCommand

from cms.api import (
    ensure_home_page_and_site,
    ensure_resource_pages,
    ensure_product_index,
    ensure_program_product_index,
)


class Command(BaseCommand):
    """Ensures that all appropriate changes have been made to Wagtail that will make the site navigable."""

    help = __doc__

    def handle(self, *args, **options):
        ensure_home_page_and_site()
        ensure_product_index()
        ensure_resource_pages()
        ensure_program_product_index()
