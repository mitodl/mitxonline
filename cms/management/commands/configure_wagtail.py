"""Ensures that all appropriate changes have been made to Wagtail that will make the site navigable."""

from django.core.management.base import BaseCommand

from cms.api import (
    ensure_certificate_index,
    ensure_home_page_and_site,
    ensure_instructors_index,
    ensure_product_index,
    ensure_program_product_index,
    ensure_resource_pages,
    ensure_signatory_index,
)


class Command(BaseCommand):
    """Ensures that all appropriate changes have been made to Wagtail that will make the site navigable."""

    help = __doc__

    def handle(self, *args, **options):  # noqa: ARG002
        ensure_home_page_and_site()
        ensure_product_index()
        ensure_resource_pages()
        ensure_program_product_index()
        ensure_signatory_index()
        ensure_certificate_index()
        ensure_instructors_index()

        from b2b.api import ensure_b2b_organization_index

        ensure_b2b_organization_index()
