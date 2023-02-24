from social_core.backends.open_id_connect import OpenIdConnectAuth


class OdlOpenIdConnectAuth(OpenIdConnectAuth):
    """
    Custom wrapper class for adding additional functionality to the
    OpenIdConnectAuth child class.
    """

    name = "odl-oidc"
