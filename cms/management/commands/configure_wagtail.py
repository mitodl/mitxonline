"""Ensures that all appropriate changes have been made to Wagtail that will make the site navigable."""
from django.core.management.base import BaseCommand

from cms.api import ensure_home_page_and_site


class Command(BaseCommand):
    """Ensures that all appropriate changes have been made to Wagtail that will make the site navigable."""

    help = __doc__

    def handle(self, *args, **options):
        ensure_home_page_and_site()
