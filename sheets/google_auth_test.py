"""
Tests for the Google auth stack behind the Sheets integrations, without mocks.

The refunds, deferrals and B2B enrollment-code sheets all authorize through
mitol.google_sheets.api.get_authorized_pygsheets_client, and their tests mock it
out. These tests load a real (generated) service-account key instead, so an
upgrade of google-auth, cryptography, pyasn1 or pygsheets that breaks loading
credentials or building the API clients fails here rather than in production.
Nothing here makes a network request.
"""

import json
import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from google.auth import jwt
from mitol.google_sheets.api import get_authorized_pygsheets_client, get_credentials
from mitol.google_sheets.constants import REQUIRED_GOOGLE_API_SCOPES

SERVICE_ACCOUNT_EMAIL = "sheets@mitxonline-test.iam.gserviceaccount.com"
TOKEN_URI = "https://oauth2.googleapis.com/token"  # noqa: S105


@pytest.fixture(scope="module")
def private_key():
    """Generate one local RSA key, like the ones Google issues for service accounts."""
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def service_account_settings(settings, private_key):
    """Configure service-account auth the way the deployed apps do."""
    settings.MITOL_GOOGLE_SHEETS_DRIVE_SERVICE_ACCOUNT_CREDS = json.dumps(
        {
            "type": "service_account",
            "project_id": "mitxonline-test",
            "private_key_id": "test-key-id",
            "private_key": private_key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ).decode(),
            "client_email": SERVICE_ACCOUNT_EMAIL,
            "client_id": "1234567890",
            "token_uri": TOKEN_URI,
        }
    )
    settings.MITOL_GOOGLE_SHEETS_ADMIN_EMAILS = [SERVICE_ACCOUNT_EMAIL]
    settings.MITOL_GOOGLE_SHEETS_GOOGLE_ACCOUNT_EMAIL_DOMAIN = "iam.gserviceaccount.com"
    settings.MITOL_GOOGLE_SHEETS_DRIVE_SHARED_ID = None


def test_service_account_credentials_sign_verifiable_tokens(
    service_account_settings,
    private_key,
):
    """The credentials should load the key and sign a JWT that its public key verifies."""
    credentials = get_credentials()

    assert credentials.service_account_email == SERVICE_ACCOUNT_EMAIL
    assert credentials.signer_email == SERVICE_ACCOUNT_EMAIL
    assert set(credentials.scopes) == set(REQUIRED_GOOGLE_API_SCOPES)

    now = int(time.time())
    token = jwt.encode(
        credentials.signer,
        {
            "iss": SERVICE_ACCOUNT_EMAIL,
            "aud": TOKEN_URI,
            "iat": now,
            "exp": now + 3600,
        },
    )
    public_key = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    claims = jwt.decode(token, certs=public_key, audience=TOKEN_URI)

    assert claims["iss"] == SERVICE_ACCOUNT_EMAIL
    assert jwt.decode_header(token)["kid"] == "test-key-id"


def test_pygsheets_client_builds_from_service_account(
    service_account_settings,
):
    """Pygsheets should build its Sheets and Drive clients from the bundled discovery docs."""
    client = get_authorized_pygsheets_client()

    assert client.oauth.service_account_email == SERVICE_ACCOUNT_EMAIL
    assert hasattr(client.sheet.service, "spreadsheets")
    assert hasattr(client.drive.service, "files")
