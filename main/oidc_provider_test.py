"""
End-to-end tests for MITx Online's OpenID Connect provider.

Open edX signs learners in through the django-oauth-toolkit provider mounted at
/oauth2/. The id_token it returns is signed with OIDC_RSA_PRIVATE_KEY by jwcrypto,
which uses cryptography. Nothing else in the suite runs that flow, so these tests
are what catch an upgrade of cryptography, jwcrypto, oauthlib or
django-oauth-toolkit that breaks signing, the published keys or token use.
"""

import json
from urllib.parse import parse_qs, urlparse

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.urls import reverse
from jwcrypto import jwk, jwt
from jwcrypto.jws import InvalidJWSSignature
from oauth2_provider.models import Application

pytestmark = [
    pytest.mark.django_db,
    # django-oauth-toolkit looks the Application up more than once per request.
    pytest.mark.skip_nplusone_check,
]

CLIENT_ID = "test-openedx-client"
CLIENT_SECRET = "test-openedx-secret"  # noqa: S105
REDIRECT_URI = "https://openedx.example.com/auth/complete/ol-oauth2/"


@pytest.fixture(scope="module")
def oidc_private_key_pem():
    """Generate one RSA key for the provider to sign id_tokens with."""
    return (
        rsa.generate_private_key(public_exponent=65537, key_size=2048)
        .private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        .decode()
    )


@pytest.fixture
def oidc_settings(settings, oidc_private_key_pem):
    """Give the provider a signing key, as OIDC_RSA_PRIVATE_KEY does when deployed."""
    settings.OAUTH2_PROVIDER = {
        **settings.OAUTH2_PROVIDER,
        "OIDC_RSA_PRIVATE_KEY": oidc_private_key_pem,
    }


@pytest.fixture
def openedx_application(oidc_settings):
    """An authorization-code client configured like the Open edX one."""
    return Application.objects.create(
        name="test-openedx",
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        client_type=Application.CLIENT_CONFIDENTIAL,
        authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
        redirect_uris=REDIRECT_URI,
        skip_authorization=True,
        algorithm=Application.RS256_ALGORITHM,
    )


def _get_id_token(client):
    """Run the authorization-code flow with the openid scope and return the token response."""
    response = client.get(
        reverse("oauth2_provider:authorize"),
        {
            "response_type": "code",
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "scope": "openid user:read",
        },
    )
    assert response.status_code == 302
    code = parse_qs(urlparse(response["Location"]).query)["code"][0]

    response = client.post(
        reverse("oauth2_provider:token"),
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
    )
    assert response.status_code == 200, response.content
    return response.json()


def test_id_token_verifies_against_published_keys(
    openedx_application,
    user_client,
    user,
):
    """The id_token should verify against the JWKS and identify the user."""
    tokens = _get_id_token(user_client)
    assert tokens["access_token"]
    assert tokens["refresh_token"]

    jwks = user_client.get(reverse("oauth2_provider:jwks-info"))
    assert jwks.status_code == 200
    keys = jwk.JWKSet.from_json(jwks.content)

    id_token = jwt.JWT(jwt=tokens["id_token"], key=keys, algs=["RS256"])
    claims = json.loads(id_token.claims)

    assert claims["aud"] == CLIENT_ID
    assert claims["sub"] == str(user.pk)
    assert claims["iss"].endswith("/oauth2")


def test_userinfo_accepts_the_access_token(
    openedx_application,
    user_client,
    client,
    user,
):
    """The access token should authorize the userinfo endpoint for the same user."""
    tokens = _get_id_token(user_client)

    response = client.get(
        reverse("oauth2_provider:user-info"),
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )

    assert response.status_code == 200
    assert response.json()["sub"] == str(user.pk)


def test_id_token_is_rejected_with_another_key(
    openedx_application,
    user_client,
):
    """Verification should fail against a key the provider didn't sign with."""
    tokens = _get_id_token(user_client)
    other_key = jwk.JWK.generate(kty="RSA", size=2048)

    with pytest.raises(InvalidJWSSignature):
        jwt.JWT(jwt=tokens["id_token"], key=other_key, algs=["RS256"])


def test_discovery_document_advertises_rs256(oidc_settings, client):
    """The discovery document should point at the JWKS and advertise RS256."""
    response = client.get(reverse("oauth2_provider:oidc-connect-discovery-info"))

    assert response.status_code == 200
    config = response.json()
    assert "RS256" in config["id_token_signing_alg_values_supported"]
    assert config["jwks_uri"].endswith(reverse("oauth2_provider:jwks-info"))
