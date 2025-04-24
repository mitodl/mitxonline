"""API functions for B2B operations."""

import logging

from django.contrib.contenttypes.models import ContentType
from wagtail.models import Page

from b2b.models import OrganizationIndexPage, OrganizationPage
from cms.api import get_home_page

log = logging.getLogger(__name__)


def ensure_b2b_organization_index() -> OrganizationIndexPage:
    """
    Ensures that an index page has been created for signatories.
    """
    home_page = get_home_page()
    org_index_page = Page.objects.filter(
        content_type=ContentType.objects.get_for_model(OrganizationIndexPage)
    ).first()
    if not org_index_page:
        org_index_page = OrganizationIndexPage(title="Organizations")
        home_page.add_child(instance=org_index_page)
        org_index_page.save_revision().publish()

    if org_index_page.get_children_count() != OrganizationPage.objects.count():
        for org_page in OrganizationPage.objects.all():
            org_page.move(org_index_page, "last-child")
        log.info("Moved organization pages under organization index page")
    return org_index_page
