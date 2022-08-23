"""Purges all pages from the Fastly cache."""
from django.core.management.base import BaseCommand

from cms.tasks import queue_fastly_full_purge


class Command(BaseCommand):
    """Purges all pages from the Fastly cache."""

    help = __doc__

    def handle(self, *args, **options):
        queue_fastly_full_purge.delay()
