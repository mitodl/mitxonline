from social_core.backends.open_id_connect import OpenIdConnectAuth


class OdlOpenIdConnectAuth(OpenIdConnectAuth):
    name = "odl-oidc"
    