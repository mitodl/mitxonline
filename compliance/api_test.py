"""Tests for compliance API helpers."""

import json
import uuid
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.core.exceptions import ImproperlyConfigured
from mitol.common.utils.datetime import now_in_utc

from compliance.api import (
    ExportComplianceResult,
    _build_export_payload,
    _normalize_administrative_area,
    decrypt_export_compliance_log,
    get_cybersource_client,
    get_latest_export_compliance_log,
    log_export_compliance_check,
    verify_user_with_exports,
)
from compliance.exceptions import ExportComplianceDataError
from compliance.factories import ExportComplianceLogFactory
from compliance.models import ExportComplianceLog
from courses.factories import CourseRunFactory
from users.factories import UserFactory
from users.models import User

pytestmark = [pytest.mark.django_db]


@pytest.fixture
def export_settings(settings, export_compliance_keypair):
    settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_MERCHANT_ID = "merchant-id"
    settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_MERCHANT_SECRET_KEY_ID = uuid.uuid4().hex
    settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_MERCHANT_SECRET = uuid.uuid4().hex
    settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_REST_API_ENVIRONMENT = (
        "apitest.cybersource.com"
    )
    return settings


def test_build_export_payload_uses_user_and_legal_address(export_settings):
    """Payload should include user identifying fields and address values."""
    user = UserFactory.create(name="Ignored Display Name", email="ada@example.com")
    user.legal_address.first_name = "Ada"
    user.legal_address.last_name = "Lovelace"
    user.legal_address.country = "US"
    user.legal_address.street_address_1 = "77 Massachusetts Ave"
    user.legal_address.street_address_2 = "Building 1"
    user.legal_address.city = "Cambridge"
    user.legal_address.state = "US-MA"
    user.legal_address.postal_code = "02139"
    user.legal_address.save()

    payload = _build_export_payload(user)

    assert payload.client_reference_information.code
    assert payload.order_information.bill_to.first_name == "Ada"
    assert payload.order_information.bill_to.last_name == "Lovelace"
    assert payload.order_information.bill_to.email == "ada@example.com"
    assert payload.order_information.bill_to.address1 == "77 Massachusetts Ave"
    assert payload.order_information.bill_to.address2 == "Building 1"
    assert payload.order_information.bill_to.locality == "Cambridge"
    assert payload.order_information.bill_to.country == "US"
    assert payload.order_information.bill_to.administrative_area == "MA"
    assert payload.order_information.bill_to.postal_code == "02139"


def test_build_export_payload_requires_cybersource_bill_to_fields(export_settings):
    """Payload creation should fail fast when required CyberSource address fields are missing."""
    user = UserFactory.create(name="Ada Lovelace", email="ada@example.com")
    user.legal_address.country = "US"
    user.legal_address.street_address_1 = ""
    user.legal_address.city = ""
    user.legal_address.state = "US-MA"
    user.legal_address.postal_code = ""
    user.legal_address.save()

    with pytest.raises(ExportComplianceDataError) as exc_info:
        _build_export_payload(user)

    assert exc_info.value.missing_fields == ["address1", "locality", "postal_code"]
    assert exc_info.value.to_error_detail() == {
        "detail": str(exc_info.value),
        "missing_fields": ["address1", "locality", "postal_code"],
    }


def test_build_export_payload_requires_legal_address(export_settings):
    """Payload creation should surface a clear, actionable error when a user has no legal address at all."""
    user = UserFactory.create(name="Ada Lovelace", email="ada@example.com")
    user.legal_address.delete()
    user = User.objects.get(pk=user.pk)

    with pytest.raises(ExportComplianceDataError) as exc_info:
        _build_export_payload(user)

    assert "contact support" in str(exc_info.value)
    assert exc_info.value.missing_fields == [
        "address1",
        "country",
        "first_name",
        "last_name",
        "locality",
    ]


def test_normalize_administrative_area_strips_country_prefix():
    """ISO-3166-2 values should be reduced to the region code for CyberSource."""
    assert _normalize_administrative_area("US", "US-MA") == "MA"
    assert _normalize_administrative_area("ca", "CA-ON") == "ON"


def test_normalize_administrative_area_preserves_non_prefixed_values():
    """Plain state values should pass through unchanged."""
    assert _normalize_administrative_area("US", "MA") == "MA"
    assert _normalize_administrative_area("US", "Massachusetts") == "Massachusetts"


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


def test_verify_user_with_exports_calls_validate_export_compliance(
    mocker, export_settings
):
    """Verification should call CyberSource, normalize the response, and cache it."""
    user = UserFactory.create(name="Ada Lovelace", email="ada@example.com")
    user.legal_address.country = "US"
    user.legal_address.street_address_1 = "77 Massachusetts Ave"
    user.legal_address.street_address_2 = "Building 1"
    user.legal_address.city = "Cambridge"
    user.legal_address.state = "US-MA"
    user.legal_address.postal_code = "02139"
    user.legal_address.save()
    run = CourseRunFactory.create()

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

    result = verify_user_with_exports(user, run)

    assert isinstance(result, ExportComplianceResult)
    assert result.accepted is True
    assert result.decision == "COMPLETED"
    assert result.reason_code == "MATCH-BCO"
    assert result.request_id == "abc123"
    mock_client.validate_export_compliance.assert_called_once()
    payload = json.loads(mock_client.validate_export_compliance.call_args.args[0])
    assert payload["order_information"]["bill_to"]["email"] == "ada@example.com"
    assert payload["order_information"]["bill_to"]["address1"] == "77 Massachusetts Ave"
    assert payload["order_information"]["bill_to"]["address2"] == "Building 1"
    assert payload["order_information"]["bill_to"]["locality"] == "Cambridge"
    assert payload["order_information"]["bill_to"]["country"] == "US"
    assert payload["order_information"]["bill_to"]["postal_code"] == "02139"
    assert payload["client_reference_information"].get("partner") is None

    log_entry = get_latest_export_compliance_log(user, run)
    assert log_entry is not None
    assert log_entry.decision == "COMPLETED"
    assert log_entry.reason_code == "MATCH-BCO"
    assert log_entry.request_id == "abc123"
    assert log_entry.courseware_object == run


def test_verify_user_with_exports_normalizes_tuple_response(mocker, export_settings):
    """Verification should handle SDK responses returned as (body, status, raw_json)."""
    user = UserFactory.create(name="Ada Lovelace", email="ada@example.com")
    user.legal_address.country = "US"
    user.legal_address.street_address_1 = "77 Massachusetts Ave"
    user.legal_address.city = "Cambridge"
    user.legal_address.state = "US-MA"
    user.legal_address.postal_code = "02139"
    user.legal_address.save()
    run = CourseRunFactory.create()

    response = (
        {
            "status": "COMPLETED",
            "id": "abc123",
            "export_compliance_information": {"info_codes": ["MATCH-BCO"]},
            "error_information": None,
            "message": None,
        },
        201,
        '{"status":"COMPLETED","id":"abc123"}',
    )
    mock_client = mocker.Mock()
    mock_client.validate_export_compliance.return_value = response
    mocker.patch("compliance.api.get_cybersource_client", return_value=mock_client)

    result = verify_user_with_exports(user, run)

    assert isinstance(result, ExportComplianceResult)
    assert result.accepted is True
    assert result.decision == "COMPLETED"
    assert result.reason_code == "MATCH-BCO"
    assert result.request_id == "abc123"
    assert result.raw == response


def test_verify_user_with_exports_uses_cached_accepted_result(mocker, export_settings):
    """An existing accepted log for the same user+run should short-circuit the CyberSource call."""
    user = UserFactory.create()
    run = CourseRunFactory.create()
    ExportComplianceLogFactory.create(
        user=user,
        courseware_object=run,
        decision="COMPLETED",
        reason_code="",
        request_id="cached-request-id",
    )
    mock_client = mocker.Mock()
    mocker.patch("compliance.api.get_cybersource_client", return_value=mock_client)

    result = verify_user_with_exports(user, run)

    mock_client.validate_export_compliance.assert_not_called()
    assert result.accepted is True
    assert result.decision == "COMPLETED"
    assert result.request_id == "cached-request-id"
    assert result.raw is None


def test_verify_user_with_exports_uses_cached_failed_result(mocker, export_settings):
    """A prior failed log for the same user+run should short-circuit the CyberSource call."""
    user = UserFactory.create()
    run = CourseRunFactory.create()
    ExportComplianceLogFactory.create(
        user=user,
        courseware_object=run,
        decision="DECLINED",
        reason_code="H10",
        request_id="cached-request-id",
    )
    mock_client = mocker.Mock()
    mocker.patch("compliance.api.get_cybersource_client", return_value=mock_client)

    result = verify_user_with_exports(user, run)

    mock_client.validate_export_compliance.assert_not_called()
    assert result.accepted is False
    assert result.decision == "DECLINED"
    assert result.request_id == "cached-request-id"
    assert result.raw is None


def test_verify_user_with_exports_uses_failed_log_for_other_stale_run(
    mocker, export_settings
):
    """A failed log for a different, stale run should still short-circuit the CyberSource call."""
    user = UserFactory.create()
    other_run = CourseRunFactory.create()
    run = CourseRunFactory.create()
    stale_log = ExportComplianceLogFactory.create(
        user=user,
        courseware_object=other_run,
        decision="DECLINED",
        reason_code="H10",
        request_id="cached-request-id",
    )
    ExportComplianceLog.objects.filter(pk=stale_log.pk).update(
        created_on=now_in_utc() - timedelta(hours=25)
    )
    mock_client = mocker.Mock()
    mocker.patch("compliance.api.get_cybersource_client", return_value=mock_client)

    result = verify_user_with_exports(user, run)

    mock_client.validate_export_compliance.assert_not_called()
    assert result.accepted is False
    assert result.decision == "DECLINED"
    assert result.request_id == "cached-request-id"


def test_verify_user_with_exports_ignores_stale_log_for_other_run(
    mocker, export_settings
):
    """An accepted log for a different run older than 24 hours should not produce a cache hit."""
    user = UserFactory.create(name="Ada Lovelace", email="ada@example.com")
    user.legal_address.country = "US"
    user.legal_address.street_address_1 = "77 Massachusetts Ave"
    user.legal_address.city = "Cambridge"
    user.legal_address.state = "US-MA"
    user.legal_address.postal_code = "02139"
    user.legal_address.save()
    other_run = CourseRunFactory.create()
    run = CourseRunFactory.create()
    stale_log = ExportComplianceLogFactory.create(
        user=user, courseware_object=other_run, decision="COMPLETED"
    )
    ExportComplianceLog.objects.filter(pk=stale_log.pk).update(
        created_on=now_in_utc() - timedelta(hours=25)
    )

    response = SimpleNamespace(
        status="COMPLETED",
        id="abc123",
        export_compliance_information=SimpleNamespace(info_codes=[]),
        error_information=None,
        message=None,
    )
    mock_client = mocker.Mock()
    mock_client.validate_export_compliance.return_value = response
    mocker.patch("compliance.api.get_cybersource_client", return_value=mock_client)

    result = verify_user_with_exports(user, run)

    mock_client.validate_export_compliance.assert_called_once()
    assert result.decision == "COMPLETED"


def test_verify_user_with_exports_uses_recent_accepted_log_for_other_run(
    mocker, export_settings
):
    """An accepted log for a different run within the last 24 hours should produce a cache hit."""
    user = UserFactory.create()
    other_run = CourseRunFactory.create()
    run = CourseRunFactory.create()
    ExportComplianceLogFactory.create(
        user=user,
        courseware_object=other_run,
        decision="COMPLETED",
        reason_code="",
        request_id="cached-request-id",
    )
    mock_client = mocker.Mock()
    mocker.patch("compliance.api.get_cybersource_client", return_value=mock_client)

    result = verify_user_with_exports(user, run)

    mock_client.validate_export_compliance.assert_not_called()
    assert result.accepted is True
    assert result.decision == "COMPLETED"
    assert result.request_id == "cached-request-id"
    assert result.raw is None


def test_decrypt_export_compliance_log_round_trips(export_compliance_keypair):
    """A logged request/response should decrypt back to its original plaintext."""
    user = UserFactory.create()
    run = CourseRunFactory.create()
    response = {
        "status": "COMPLETED",
        "id": "abc123",
        "export_compliance_information": {"info_codes": []},
        "error_information": None,
        "message": None,
    }
    result = ExportComplianceResult(
        decision="COMPLETED", reason_code=None, request_id="abc123", raw=response
    )

    log_entry = log_export_compliance_check(
        user, run, '{"hello": "world"}', response, result
    )

    decrypted = decrypt_export_compliance_log(log_entry, export_compliance_keypair)
    assert decrypted.request == '{"hello": "world"}'
    assert json.loads(decrypted.response) == response
