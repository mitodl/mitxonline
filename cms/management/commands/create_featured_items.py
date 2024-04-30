"""Management command to manually pull a new set of featured items for the CMS home page"""
from django.core.management.base import BaseCommand

from cms.api import create_featured_items


class Command(BaseCommand):
    """Management command to manually pull a new set of featured items for the CMS home page"""

    help = __doc__

    def handle(self, *args, **kwargs):
        create_featured_items()
