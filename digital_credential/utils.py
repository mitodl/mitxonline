from copy import deepcopy
from urllib.parse import urljoin

from django.conf import settings

from digital_credential.constants import VERIFY_REQUEST_BODY


def dc_url(path):
    """Returns the full url to the provided path"""
    return urljoin(settings.DIGITAL_CREDENTAL_COORDINATOR_URL, path)


def create_verify_payload(credential_id):
    """
    Returns a copy of VERIFY_REQUEST_BODY with the credential_id set in the payload.
    """
    payload = deepcopy(VERIFY_REQUEST_BODY)
    payload["verifiableCredential"]["id"] = credential_id
    return payload
