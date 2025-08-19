"""
Code for working with Keycloak

Some data we need that's stored in Keycloak is best retrieved by using its own
API, rather than using SCIM or relying on the OIDC payload. At the moment, this
is mostly the organizations data.
"""

from urllib.parse import urljoin

from django.conf import settings
from oauthlib.oauth2 import BackendApplicationClient
from requests_oauthlib import OAuth2Session


class KeycloakAdminClient:
    """Client for the Keycloak admin API."""

    token = None
    oauth_session = None

    def _preflight(self):
        """Update the auth token as a pre-flight step before sending any requests."""

        token_url = urljoin(settings.KEYCLOAK_BASE_URL, settings.KEYCLOAK_ADMIN_REALM_TOKEN_ENDPOINT)

        client = BackendApplicationClient(client_id=settings.KEYCLOAK_CLIENT_ID)
        self.oauth_session = OAuth2Session(client=client)
        self.token = self.oauth_session.fetch_token(
            token_url=token_url,
            client_id=settings.KEYCLOAK_CLIENT_ID,
            client_secret=settings.KEYCLOAK_CLIENT_SECRET,
        )

    def get(self, url_path, **kwargs):
        """Perform a GET request against the given URL path."""

        self._preflight()
        return self.oauth_session.get(
            urljoin(settings.KEYCLOAK_BASE_URL, url_path),
            **kwargs
        ) if self.oauth_session else None

    def post(self, url_path, **kwargs):
        """Perform a POST request against the given URL path."""

        self._preflight()
        return self.oauth_session.post(
            urljoin(settings.KEYCLOAK_BASE_URL, url_path),
            **kwargs
        ) if self.oauth_session else None
