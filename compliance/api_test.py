"""Tests for compliance API helpers."""

from types import SimpleNamespace

import pytest
from django.core.exceptions import ImproperlyConfigured

from compliance.api import (
    ExportComplianceResult,
    _build_export_payload,
    get_cybersource_client,
    verify_user_with_exports,
)
from users.factories import UserFactory

pytestmark = [pytest.mark.django_db]


@pytest.fixture
def export_settings(settings):
    settings.CYBERSOURCE_WSDL_URL = "https://example.com/cybersource?wsdl"
    settings.CYBERSOURCE_MERCHANT_ID = "merchant-id"
    settings.CYBERSOURCE_TRANSACTION_KEY = "transaction-key"
    settings.CYBERSOURCE_EXPORT_SERVICE_RUN = True
    return settings


def test_build_export_payload_uses_user_and_legal_address(export_settings):
    """Payload should include user identifying fields and address values."""
    user = UserFactory.create(name="Ada Lovelace", email="ada@example.com")
    user.legal_address.country = "US"
    user.legal_address.state = "US-MA"
    user.legal_address.save()
    payload = _build_export_payload(user)
    assert payload["merchantID"] == "merchant-id"
    assert payload["exportService"] == {"run": "true"}
    assert payload["billTo"] == {
        "firstName": "Ada",
        "lastName": "Lovelace",
        "email": "ada@example.com",
        "country": "US",
        "administrativeArea": "US-MA",
    }


def test_get_cybersource_client_requires_configuration(settings):
    """Client creation should fail if required settings are missing."""
    settings.CYBERSOURCE_WSDL_URL = ""
    settings.CYBERSOURCE_MERCHANT_ID = ""
    settings.CYBERSOURCE_TRANSACTION_KEY = ""
    with pytest.raises(ImproperlyConfigured):
        get_cybersource_client()


def test_get_cybersource_client_requires_zeep(mocker, export_settings):
    """Client creation should surface a clear error if zeep is unavailable."""
    real_import = __import__

    def mocked_import(name, *args, **kwargs):
        if name == "zeep" or name.startswith("zeep."):
            raise ModuleNotFoundError(name)
        return real_import(name, *args, **kwargs)

    mocker.patch("builtins.__import__", side_effect=mocked_import)
    with pytest.raises(ImproperlyConfigured, match="zeep must be installed"):
        get_cybersource_client()


def test_verify_user_with_exports_calls_run_transaction(mocker, export_settings):
    """Verification should call CyberSource and normalize the response."""
    user = UserFactory.create(name="Ada Lovelace", email="ada@example.com")
    user.legal_address.country = "US"
    user.legal_address.state = "US-MA"
    user.legal_address.save()
    response = SimpleNamespace(decision="ACCEPT", reasonCode=100, requestID="abc123")
    mock_client = mocker.Mock()
    mock_client.service.runTransaction.return_value = response
    mocker.patch("compliance.api.get_cybersource_client", return_value=mock_client)
    result = verify_user_with_exports(user)
    assert isinstance(result, ExportComplianceResult)
    assert result.accepted is True
    assert result.decision == "ACCEPT"
    assert result.reason_code == 100
    assert result.request_id == "abc123"
    mock_client.service.runTransaction.assert_called_once()
