"""
Code for working with Keycloak

Some data we need that's stored in Keycloak is best retrieved by using its own
API, rather than using SCIM or relying on the OIDC payload. At the moment, this
is mostly the organizations data.
"""

from urllib.parse import urljoin

import requests
from authlib.integrations.requests_client import OAuth2Session
from django.conf import settings

from b2b.exceptions import KeycloakAdminImproperlyConfiguredError


class KeycloakAdminClient:
    """Client for the Keycloak admin API."""

    base_url = None
    realm = None
    oauth_session = None

    def __init__(self):
        """
        Configure the client so we can use it.

        These settings must be in place:
        - KEYCLOAK_BASE_URL: The base URL for the Keycloak instance.
        - KEYCLOAK_DISCOVERY_URL: The OpenID discovery URL for the realm.
        - KEYCLOAK_CLIENT_ID: The client ID to use for the admin client.
        - KEYCLOAK_CLIENT_SECRET: The client secret to use for the admin client.
        - KEYCLOAK_REALM: The realm we are working with.

        If any of these are incorrect or missing, you'll get an
        KeycloakAdminImproperlyConfiguredError.

        The client should be one that has the ability to use the admin API. The
        regular authentication client may not have this permission.
        """

        self.base_url = settings.get("KEYCLOAK_BASE_URL", None)
        if not self.base_url:
            msg = "KEYCLOAK_BASE_URL setting is not configured."
            raise KeycloakAdminImproperlyConfiguredError(msg)
        self.base_url = urljoin(self.base_url, "/admin/realms")
        self.realm = settings.get("KEYCLOAK_REALM", None)
        if not self.realm:
            msg = "KEYCLOAK_REALM setting is not configured."
            raise KeycloakAdminImproperlyConfiguredError(msg)

        realm_discovery = settings.get("KEYCLOAK_DISCOVERY_URL", None)
        if not realm_discovery:
            msg = "KEYCLOAK_DISCOVERY_URL setting is not configured."
            raise KeycloakAdminImproperlyConfiguredError(msg)
        client_id = settings.get("KEYCLOAK_CLIENT_ID", None)
        if not client_id:
            msg = "KEYCLOAK_CLIENT_ID setting is not configured."
            raise KeycloakAdminImproperlyConfiguredError(msg)
        client_secret = settings.get("KEYCLOAK_CLIENT_SECRET", None)
        if not client_secret:
            msg = "KEYCLOAK_CLIENT_SECRET setting is not configured."
            raise KeycloakAdminImproperlyConfiguredError(msg)

        openid_configuration = requests.get(realm_discovery, timeout=60).json()
        openid_configuration.raise_for_status()
        self.oauth_session = OAuth2Session(
            client_id=client_id,
            client_secret=client_secret,
            token_endpoint=openid_configuration["token_endpoint"],
        )

    def realmify_url(self, url_path):
        """
        Prefix the given URL path with the realm base path.

        The admin API URLs are all /admin/realms/ and then _usually_ a realm
        name.

        Args:
        - url_path: The URL path to prefix with the realm base path.
        Returns:
        - The full URL path with the realm base path prefixed.
        """

        return urljoin(self.base_url, f"{self.realm}/{url_path}")

    def request(self, method, url_path, **kwargs):
        """Perform an HTTP request against the given URL path."""

        return (
            self.oauth_session.request(method, self.realmify_url(url_path), **kwargs)
            if self.oauth_session
            else None
        )
