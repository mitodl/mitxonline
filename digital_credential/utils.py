from urllib.parse import urljoin

from django.conf import settings


def dc_url(path):
    """Returns the full url to the provided path"""
    return urljoin(settings.DIGITAL_CREDENTAL_COORDINATOR_URL, path)
