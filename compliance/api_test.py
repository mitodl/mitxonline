"""Tests for compliance API helpers."""

import json
import uuid
from types import SimpleNamespace

import pytest
from django.core.exceptions import ImproperlyConfigured

import compliance.api as compliance_api
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
    settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_MERCHANT_ID = "merchant-id"
    settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_MERCHANT_SECRET_KEY_ID = uuid.uuid4().hex
    settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_MERCHANT_SECRET = uuid.uuid4().hex
    settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_REST_API_ENVIRONMENT = (
        "apitest.cybersource.com"
    )
    return settings


def test_build_export_payload_uses_user_and_legal_address(export_settings):
    """Payload should include user identifying fields and address values."""
    user = UserFactory.create(name="Ada Lovelace", email="ada@example.com")
    user.legal_address.country = "US"
    user.legal_address.state = "US-MA"
    user.legal_address.save()

    payload = _build_export_payload(user)

    assert payload.client_reference_information.code
    assert payload.order_information.bill_to.first_name == "Ada"
    assert payload.order_information.bill_to.last_name == "Lovelace"
    assert payload.order_information.bill_to.email == "ada@example.com"
    assert payload.order_information.bill_to.country == "US"
    assert payload.order_information.bill_to.administrative_area == "US-MA"


def test_get_cybersource_client_requires_configuration(settings):
    """Client creation should fail if required settings are missing."""
    settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_MERCHANT_ID = ""
    settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_MERCHANT_SECRET_KEY_ID = ""
    settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_MERCHANT_SECRET = ""
    settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_REST_API_ENVIRONMENT = ""
    with pytest.raises(
        ImproperlyConfigured,
        match="MITOL_PAYMENT_GATEWAY_CYBERSOURCE_MERCHANT_ID must be configured",
    ):
        get_cybersource_client()


def test_get_cybersource_client_uses_official_rest_sdk_configuration(export_settings):
    """Client creation should use the official CyberSource REST SDK config keys."""
    client = get_cybersource_client()

    assert client.api_client.mconfig.authentication_type == "HTTP_SIGNATURE"
    assert client.api_client.mconfig.merchant_id == "merchant-id"
    assert client.api_client.mconfig.run_environment == "apitest.cybersource.com"


def test_get_cybersource_client_requires_cybersource_sdk(mocker, export_settings):
    """Client creation should surface a clear error if the CyberSource SDK is unavailable."""
    mocker.patch.object(
        compliance_api,
        "_CYBERSOURCE_IMPORT_ERROR",
        ModuleNotFoundError("CyberSource"),
    )
    with pytest.raises(
        ImproperlyConfigured,
        match="CyberSource SDK must be installed",
    ):
        get_cybersource_client()


def test_verify_user_with_exports_calls_validate_export_compliance(
    mocker, export_settings
):
    """Verification should call CyberSource and normalize the response."""
    user = UserFactory.create(name="Ada Lovelace", email="ada@example.com")
    user.legal_address.country = "US"
    user.legal_address.state = "US-MA"
    user.legal_address.save()

    response = SimpleNamespace(
        status="COMPLETED",
        id="abc123",
        export_compliance_information=SimpleNamespace(info_codes=["MATCH-BCO"]),
        error_information=None,
        message=None,
    )
    mock_client = mocker.Mock()
    mock_client.validate_export_compliance.return_value = response
    mocker.patch("compliance.api.get_cybersource_client", return_value=mock_client)

    result = verify_user_with_exports(user)

    assert isinstance(result, ExportComplianceResult)
    assert result.accepted is True
    assert result.decision == "COMPLETED"
    assert result.reason_code == "MATCH-BCO"
    assert result.request_id == "abc123"
    mock_client.validate_export_compliance.assert_called_once()
    payload = json.loads(mock_client.validate_export_compliance.call_args.args[0])
    assert payload["order_information"]["bill_to"]["email"] == "ada@example.com"
    assert payload["order_information"]["bill_to"]["country"] == "US"
    assert payload["client_reference_information"].get("partner") is None
