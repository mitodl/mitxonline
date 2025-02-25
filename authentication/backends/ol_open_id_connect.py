"""Keycloak Authentication Configuration"""

import logging

from social_core.backends.open_id_connect import OpenIdConnectAuth

log = logging.getLogger(__name__)


class OlOpenIdConnectAuth(OpenIdConnectAuth):
    """
    Custom wrapper class for adding additional functionality to the
    OpenIdConnectAuth child class.
    """

    name = "ol-oidc"
    REQUIRES_EMAIL_VALIDATION = False

    def get_user_details(self, response):
        """Get the user details from the API response"""
        details = super().get_user_details(response)

        log.error("User details: %s", details)
        log.error("Response: %s", response)

        returnable = {
            **details,
            "global_id": response.get("sub", None),
            "name": response.get("name", "we didn't get a name for some reason"),
            "is_active": True,
            "profile": {
                "name": response.get("name", ""),
                "email_optin": bool(int(response["email_optin"]))
                if "email_optin" in response
                else None,
            },
        }

        log.error("Returning: %s", returnable)
        return returnable

    def __str__(self):
        return "OL OpenID Connect (ol-oidc)"
