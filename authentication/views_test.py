"""Tests for authentication views"""

import pytest


@pytest.mark.django_db
def test_well_known_openid_configuration(client, settings):
    """Test that .well-known/openid-configuration returns the right data"""
    settings.SITE_BASE_URL = "http://mitx-online.local"
    resp = client.get("/.well-known/openid-configuration")
    assert resp.json() == {
        "issuer": "http://mitx-online.local",
        "authorization_endpoint": "http://mitx-online.local/oauth2/authorize/",
        "token_endpoint": "http://mitx-online.local/oauth2/token/",
        "userinfo_endpoint": "http://mitx-online.local/api/userinfo",
    }
