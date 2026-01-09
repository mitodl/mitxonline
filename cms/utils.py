from django.conf import settings
from django.urls import reverse


def get_page_editing_url(page_id: int) -> str:
    """
    Return the URL for editing a Wagtail page with the given ID.
    """
    return (
        f"{settings.SITE_BASE_URL.rstrip('/')}"
        f"{reverse('wagtailadmin_pages:edit', args=[page_id])}"
    )
