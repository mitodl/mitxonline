"""Management command to manually pull a new set of featured items for the CMS home page"""

from django.core.management.base import BaseCommand

from cms.api import create_featured_items


class Command(BaseCommand):
    """Management command to manually pull a new set of featured items for the CMS home page"""

    help = __doc__

    def handle(self, *args, **options):  # pylint: disable=unused-argument  # noqa: ARG002
        self.stdout.write("Generating new featured courses for the CMS home page")
        featured_courses = create_featured_items()
        self.stdout.write("Featured courses set in cache")
        for featured_course in featured_courses:
            self.stdout.write(f"{featured_course}")
