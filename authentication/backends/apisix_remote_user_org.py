"""
The APISIX Remote User Backend, with organization support.

This should go in the ol-django app. It's here to make it easier to write.
"""

import base64
import binascii
import json
import logging

from mitol.apigateway.api import decode_x_header
from mitol.apigateway.backends import ApisixRemoteUserBackend

from b2b.api import reconcile_user_orgs

log = logging.getLogger(__name__)

ID_TOKEN_HEADER_NAME = "HTTP_X_ID_TOKEN"  # noqa: S105


def _b64decode_json(value: str) -> dict:
    """Decode a base64 (standard or URL-safe, padding optional) JSON value."""

    padded = value + "=" * (-len(value) % 4)
    return json.loads(
        base64.urlsafe_b64decode(padded.replace("+", "-").replace("/", "_"))
    )


def decode_id_token_header(request) -> dict | None:
    """
    Decode the ID token claims APISIX passes along in X-ID-Token.

    APISIX sends the ID token's claims as base64-encoded JSON, the same way it
    sends X-Userinfo. If it's a raw JWT instead, the payload segment is used.
    The signature isn't checked: like X-Userinfo, this header is trusted
    because it comes from APISIX.

    Args:
    - request (HttpRequest): the request

    Returns:
    - dict of ID token claims, or None if the header is missing or unreadable
    """

    header = request.META.get(ID_TOKEN_HEADER_NAME)

    if not header:
        return None

    try:
        segments = header.split(".")
        claims = _b64decode_json(segments[1] if len(segments) == 3 else header)  # noqa: PLR2004
    except (binascii.Error, UnicodeDecodeError, ValueError):
        log.warning("Unable to decode the %s header", ID_TOKEN_HEADER_NAME)
        return None

    return claims if isinstance(claims, dict) else None


def get_session_auth_time(request) -> int | None:
    """
    Get the time the user authenticated for this APISIX session.

    X-Userinfo doesn't carry any session claims, so this comes from the ID
    token. auth_time is when the user authenticated with Keycloak, which stays
    the same for the life of the session; iat is used if it's not there.

    Returns:
    - int, seconds since the epoch, or None if we can't tell
    """

    claims = decode_id_token_header(request)

    if not claims:
        return None

    auth_time = claims.get("auth_time", claims.get("iat"))

    try:
        return int(auth_time) if auth_time is not None else None
    except (TypeError, ValueError):
        return None


class ApisixRemoteUserOrgBackend(ApisixRemoteUserBackend):
    """
    Updates the APISIX remote user backend to work with organizations.

    We should get the organizations that the user belongs to in the APISIX
    payload, so we should reconcile them (occasionally, maybe) when the user gets
    here. SCIM should also take care of this but we won't necessarily have that
    for local deployments.
    """

    def configure_user(self, request, user, *args, created=True):
        """Configure the user, then reconcile the orgs."""

        user = super().configure_user(request, user, *args, created=created)

        apisix_header = decode_x_header(request)

        org_uuids = []

        if apisix_header and "organization" in apisix_header:
            org_uuids = [
                apisix_header["organization"][org]["id"]
                for org in apisix_header["organization"]
            ]

        # Task should check to see if it needs to run or not
        reconcile_user_orgs(
            user, org_uuids, session_auth_time=get_session_auth_time(request)
        )

        return user
