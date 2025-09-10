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
from b2b.keycloak_admin_dataclasses import OrganizationRepresentation


class KeycloakAdminClient:
    """Client for the Keycloak admin API."""

    base_url = None
    realm = None
    oauth_session = None
    skip_verify = False

    def __init__(self):
        """
        Configure the client so we can use it.

        These settings must be in place:
        - KEYCLOAK_BASE_URL: The base URL for the Keycloak instance.
        - KEYCLOAK_DISCOVERY_URL: The OpenID discovery URL for the realm.
        - KEYCLOAK_ADMIN_CLIENT_ID: The client ID to use for the admin client.
        - KEYCLOAK_ADMIN_CLIENT_SECRET: The client secret to use for the admin client.
        - KEYCLOAK_REALM_NAME: The realm we are working with.

        If any of these are incorrect or missing, you'll get an
        KeycloakAdminImproperlyConfiguredError.

        The client should be one that has the ability to use the admin API. The
        regular authentication client may not have this permission.
        """

        self.base_url = settings.KEYCLOAK_BASE_URL
        if not self.base_url:
            msg = "KEYCLOAK_BASE_URL setting is not configured."
            raise KeycloakAdminImproperlyConfiguredError(msg)
        self.base_url = urljoin(self.base_url, "/admin/realms")
        self.realm = settings.KEYCLOAK_REALM_NAME
        if not self.realm:
            msg = "KEYCLOAK_REALM_NAME setting is not configured."
            raise KeycloakAdminImproperlyConfiguredError(msg)

        realm_discovery = settings.KEYCLOAK_DISCOVERY_URL
        if not realm_discovery:
            msg = "KEYCLOAK_DISCOVERY_URL setting is not configured."
            raise KeycloakAdminImproperlyConfiguredError(msg)
        client_id = settings.KEYCLOAK_ADMIN_CLIENT_ID
        if not client_id:
            msg = "KEYCLOAK_ADMIN_CLIENT_ID setting is not configured."
            raise KeycloakAdminImproperlyConfiguredError(msg)
        client_secret = settings.KEYCLOAK_ADMIN_CLIENT_SECRET
        if not client_secret:
            msg = "KEYCLOAK_ADMIN_CLIENT_SECRET setting is not configured."
            raise KeycloakAdminImproperlyConfiguredError(msg)

        self.skip_verify = settings.KEYCLOAK_ADMIN_CLIENT_NO_VERIFY_SSL or False

        openid_configuration = requests.get(
            realm_discovery,
            timeout=60,
            verify=not self.skip_verify,
        )
        openid_configuration.raise_for_status()
        self.openid_configuration = openid_configuration.json()

        self.oauth_session = OAuth2Session(
            client_id=client_id,
            client_secret=client_secret,
            token_endpoint=self.openid_configuration["token_endpoint"],
            scope=settings.KEYCLOAK_ADMIN_CLIENT_SCOPES,
            verify=not self.skip_verify,
        )
        self.token = self.oauth_session.fetch_token(
            self.openid_configuration["token_endpoint"],
            grant_type="client_credentials",
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

    def request(self, method, url_path, *, skip_realmify=False, **kwargs):
        """Perform an HTTP request against the given URL path."""

        request_url = (
            urljoin(self.base_url, url_path)
            if skip_realmify
            else self.realmify_url(url_path)
        )

        return (
            self.oauth_session.request(method, request_url, **kwargs)
            if self.oauth_session
            else None
        )


class KeycloakAdminOrganization:
    """Client for working with Keycloak organizations via the admin API."""

    def __init__(self, admin_client):
        """
        Configure the organization client.

        Args:
        - admin_client: An instance of KeycloakAdminClient.
        """

        self.admin_client = admin_client

    def list(self, **kwargs):
        """
        List all organizations in the realm.

        Keyword Args:
        - exact: bool; If True, only return exact matches for the search term
        - search: str; A search term to filter organizations by name or description.
        - q: str; Search by attribute values ("key:value key:value").
        Returns:
        - A list of OrganizationRepresentation instances.
        """

        response = self.admin_client.request("GET", "organizations", params=kwargs)
        response.raise_for_status()
        orgs_data = response.json()

        return [OrganizationRepresentation(**org) for org in orgs_data]

    def get(self, org_id):
        """
        Get a single organization by its ID.

        Args:
        - org_id: The ID of the organization to retrieve.

        Returns:
        - An instance of OrganizationRepresentation.
        """

        response = self.admin_client.request("GET", f"organizations/{org_id}")
        response.raise_for_status()
        org_data = response.json()

        return OrganizationRepresentation(**org_data)
