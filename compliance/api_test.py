"""Tests for compliance API helpers."""

import json
import uuid
from datetime import timedelta
from types import SimpleNamespace

import pytest
import sentry_sdk
from CyberSource.rest import ApiException
from django.core.exceptions import ImproperlyConfigured
from mitol.common.utils.datetime import now_in_utc

from compliance.api import (
    ExportComplianceResult,
    _build_export_payload,
    _normalize_administrative_area,
    decrypt_export_compliance_log,
    get_cybersource_client,
    get_latest_export_compliance_log,
    get_missing_export_compliance_fields,
    get_unresolved_export_compliance_decline,
    log_export_compliance_check,
    verify_user_with_exports,
)
from compliance.exceptions import (
    BILL_TO_FIELD_TO_PROFILE_FIELD,
    ExportComplianceDataError,
)
from compliance.factories import ExportComplianceLogFactory
from compliance.models import ExportComplianceDecision, ExportComplianceLog
from courses.factories import CourseRunFactory
from main.sentry import EXPORT_COMPLIANCE_USER_TAG, before_send
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


def test_build_export_payload_does_not_require_state_and_postal_code_outside_us_ca(
    export_settings,
):
    """CyberSource itself only requires state/postal code for US and CA addresses."""
    user = UserFactory.create(name="Ada Lovelace", email="ada@example.com")
    user.legal_address.country = "FR"
    user.legal_address.street_address_1 = "5 Rue de Rivoli"
    user.legal_address.city = "Paris"
    user.legal_address.state = ""
    user.legal_address.postal_code = ""
    user.legal_address.save()

    payload = _build_export_payload(user)

    assert payload.order_information.bill_to.country == "FR"


def test_get_missing_export_compliance_fields_always_flags_state_and_postal_code():
    """
    The profile-facing missing fields list should flag state/postal code
    whenever they're empty, even for countries where CyberSource doesn't
    require them.
    """
    user = UserFactory.create(name="Ada Lovelace", email="ada@example.com")
    user.legal_address.country = "FR"
    user.legal_address.street_address_1 = "5 Rue de Rivoli"
    user.legal_address.city = "Paris"
    user.legal_address.state = ""
    user.legal_address.postal_code = ""
    user.legal_address.save()

    assert get_missing_export_compliance_fields(user) == ["postal_code", "state"]


def test_get_missing_export_compliance_fields_us_address():
    """State/postal code should still be flagged as missing for US addresses."""
    user = UserFactory.create(name="Ada Lovelace", email="ada@example.com")
    user.legal_address.country = "US"
    user.legal_address.street_address_1 = "77 Massachusetts Ave"
    user.legal_address.city = "Cambridge"
    user.legal_address.state = ""
    user.legal_address.postal_code = ""
    user.legal_address.save()

    assert get_missing_export_compliance_fields(user) == ["postal_code", "state"]


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


def _set_us_legal_address(user):
    """Give the user the legal address a live CyberSource check needs."""
    user.legal_address.first_name = "Ada"
    user.legal_address.last_name = "Lovelace"
    user.legal_address.country = "US"
    user.legal_address.street_address_1 = "77 Massachusetts Ave"
    user.legal_address.city = "Cambridge"
    user.legal_address.state = "US-MA"
    user.legal_address.postal_code = "02139"
    user.legal_address.save()


def test_failed_check_does_not_send_learner_data_to_sentry(mocker, export_settings):
    """A CyberSource error captured by the real Sentry SDK keeps the bill-to out of Sentry."""
    user = UserFactory.create(name="Ada Lovelace", email="ada@example.com")
    _set_us_legal_address(user)
    run = CourseRunFactory.create()

    mock_client = mocker.Mock()
    mock_client.validate_export_compliance.side_effect = ApiException(
        status=400, reason="Bad Request"
    )
    mocker.patch("compliance.api.get_cybersource_client", return_value=mock_client)

    events = []
    sentry_sdk.init(
        dsn="https://k@o0.ingest.sentry.io/0",
        # Keep the unscrubbed event; before_send runs on it below
        before_send=lambda event, _hint: events.append(event),
        default_integrations=False,
    )
    try:
        with sentry_sdk.isolation_scope():
            # What DjangoIntegration attaches for the request user
            sentry_sdk.set_user(
                {"id": str(user.pk), "email": user.email, "username": user.username}
            )
            with pytest.raises(ApiException) as excinfo:
                verify_user_with_exports(user, run)
            sentry_sdk.capture_exception(excinfo.value)
        sentry_sdk.flush()
    finally:
        sentry_sdk.get_global_scope().set_client(None)

    assert len(events) == 1
    # This test's own frame and ApiException's module (CyberSource.rest) would
    # each trigger the strip, so drop both: the compliance.api frame must be
    # enough on its own.
    exception = events[0]["exception"]["values"][0]
    frames = exception["stacktrace"]["frames"]
    frames[:] = [frame for frame in frames if frame.get("module") != __name__]
    assert "compliance.api" in [frame.get("module") for frame in frames]
    exception.pop("module")

    event = before_send(events[0], {})
    event_json = json.dumps(event)
    assert "verify_user_with_exports" in event_json
    assert event["user"] == {"id": user.global_id}
    for value in [
        "ada@example.com",
        user.username,
        "Lovelace",
        "77 Massachusetts Ave",
        "02139",
    ]:
        assert value not in event_json


def test_cached_check_tags_the_current_learner(mocker, export_settings):
    """A cache hit after a live check reports the learner being checked, not the last one."""
    live_user = UserFactory.create()
    _set_us_legal_address(live_user)
    cached_user = UserFactory.create()
    run = CourseRunFactory.create()
    ExportComplianceLogFactory.create(
        user=cached_user, courseware_object=run, decision="COMPLETED"
    )
    mock_client = mocker.Mock()
    mock_client.validate_export_compliance.return_value = SimpleNamespace(
        status="COMPLETED",
        id="abc123",
        export_compliance_information=SimpleNamespace(info_codes=[]),
        error_information=None,
        message=None,
    )
    mocker.patch("compliance.api.get_cybersource_client", return_value=mock_client)

    with sentry_sdk.isolation_scope() as scope:
        verify_user_with_exports(live_user, run)
        verify_user_with_exports(cached_user, run)

        mock_client.validate_export_compliance.assert_called_once()
        assert scope._tags[EXPORT_COMPLIANCE_USER_TAG] == cached_user.global_id  # noqa: SLF001


COMPLETED = ExportComplianceDecision.COMPLETED
DECLINED = ExportComplianceDecision.DECLINED
INVALID_REQUEST = ExportComplianceDecision.INVALID_REQUEST
MANUALLY_APPROVED = ExportComplianceDecision.MANUALLY_APPROVED


@pytest.mark.parametrize(
    ("decisions", "blocking_index"),
    [
        ([], None),
        ([COMPLETED], None),
        ([INVALID_REQUEST], None),
        ([DECLINED], 0),
        ([DECLINED, COMPLETED], None),
        ([COMPLETED, DECLINED], 1),
        ([DECLINED, INVALID_REQUEST], 0),
        ([DECLINED, COMPLETED, DECLINED], 2),
        ([DECLINED, MANUALLY_APPROVED], None),
    ],
)
def test_get_unresolved_export_compliance_decline(decisions, blocking_index):
    """Only the most recent DECLINED log with no later accepted log counts"""
    user = UserFactory.create()
    other_user = UserFactory.create()
    ExportComplianceLogFactory.create(user=other_user, decision=DECLINED)
    start = now_in_utc() - timedelta(days=len(decisions) + 1)
    logs = []
    for index, decision in enumerate(decisions):
        extra_log_kwargs = {}
        if decision == MANUALLY_APPROVED:
            extra_log_kwargs["approved_by"] = UserFactory.create()
            extra_log_kwargs["approved_on"] = start + timedelta(days=index)
        log_entry = ExportComplianceLogFactory.create(
            user=user, decision=decision, **extra_log_kwargs
        )
        ExportComplianceLog.objects.filter(pk=log_entry.pk).update(
            created_on=start + timedelta(days=index)
        )
        logs.append(log_entry)

    expected = None if blocking_index is None else logs[blocking_index]
    assert get_unresolved_export_compliance_decline(user) == expected


def _complete_user():
    """Return a user whose legal address passes the pre-request field check."""
    user = UserFactory.create()
    user.legal_address.country = "US"
    user.legal_address.state = "US-MA"
    user.legal_address.save()
    return user


def _invalid_request(details, status=400, body_status="INVALID_REQUEST"):
    """Build the ApiException the CyberSource SDK raises for a rejected request."""
    body = json.dumps(
        {
            "id": "7915649045806763404884",
            "status": body_status,
            "reason": "INVALID_DATA",
            "message": "Declined - One or more fields in the request contains invalid data",
            "details": details,
        }
    )
    return ApiException(
        http_resp=SimpleNamespace(
            status=status, reason="Bad Request", data=body, getheaders=dict
        )
    )


REQUIRED_BILL_TO_FIELDS = sorted(
    [
        "first_name",
        "last_name",
        "email",
        "address1",
        "locality",
        "country",
        "administrative_area",
        "postal_code",
    ]
)
REQUIRED_PROFILE_FIELDS = sorted(
    BILL_TO_FIELD_TO_PROFILE_FIELD[f] for f in REQUIRED_BILL_TO_FIELDS
)


@pytest.mark.parametrize(
    ("details", "expected_fields", "expected_profile_fields"),
    [
        (
            [{"field": "orderInformation.billTo.lastName", "reason": "INVALID_DATA"}],
            ["last_name"],
            ["last_name"],
        ),
        (
            [
                {
                    "field": "orderInformation.billTo.postalCode",
                    "reason": "MISSING_FIELD",
                },
                {"field": "orderInformation.billTo.address1", "reason": "INVALID_DATA"},
            ],
            ["address1", "postal_code"],
            ["postal_code", "street_address_1"],
        ),
        (
            [{"field": "orderInformation.billTo.address2", "reason": "INVALID_DATA"}],
            ["address2"],
            ["street_address_2"],
        ),
        # No usable field named - ask the user to review all the required ones
        ([], REQUIRED_BILL_TO_FIELDS, REQUIRED_PROFILE_FIELDS),
        (
            [{"field": "orderInformation.somethingElse", "reason": "MISSING_FIELD"}],
            REQUIRED_BILL_TO_FIELDS,
            REQUIRED_PROFILE_FIELDS,
        ),
    ],
)
def test_verify_user_with_exports_maps_invalid_request_to_data_error(
    mocker, export_settings, details, expected_fields, expected_profile_fields
):
    """A 400 INVALID_REQUEST names the profile fields to fix and caches nothing."""
    user = _complete_user()
    run = CourseRunFactory.create()
    mock_client = mocker.Mock()
    mock_client.validate_export_compliance.side_effect = _invalid_request(details)
    mocker.patch("compliance.api.get_cybersource_client", return_value=mock_client)

    with pytest.raises(ExportComplianceDataError) as exc_info:
        verify_user_with_exports(user, run)

    assert exc_info.value.missing_fields == expected_fields
    assert exc_info.value.profile_fields == expected_profile_fields
    assert not ExportComplianceLog.objects.filter(user=user).exists()


@pytest.mark.parametrize(
    ("details", "logs_error"),
    [
        (
            [{"field": "orderInformation.billTo.lastName", "reason": "INVALID_DATA"}],
            False,
        ),
        (
            [{"field": "orderInformation.somethingElse", "reason": "MISSING_FIELD"}],
            True,
        ),
    ],
)
def test_verify_user_with_exports_logs_unattributable_rejections(
    mocker, export_settings, caplog, details, logs_error
):
    """A rejection naming no field we know is logged as an error, to be noticed."""
    mock_client = mocker.Mock()
    mock_client.validate_export_compliance.side_effect = _invalid_request(details)
    mocker.patch("compliance.api.get_cybersource_client", return_value=mock_client)

    with pytest.raises(ExportComplianceDataError):
        verify_user_with_exports(_complete_user(), CourseRunFactory.create())

    errors = [r for r in caplog.records if r.levelname == "ERROR"]
    assert bool(errors) is logs_error
    if logs_error:
        assert "orderInformation.somethingElse" in errors[0].getMessage()


@pytest.mark.parametrize(
    ("status", "body_status"),
    [(401, "INVALID_REQUEST"), (500, "SERVER_ERROR"), (400, "DECLINED")],
)
def test_verify_user_with_exports_reraises_other_api_errors(
    mocker, export_settings, status, body_status
):
    """Auth failures and outages are not the user's to fix, so they still raise."""
    user = _complete_user()
    run = CourseRunFactory.create()
    mock_client = mocker.Mock()
    mock_client.validate_export_compliance.side_effect = _invalid_request(
        [], status=status, body_status=body_status
    )
    mocker.patch("compliance.api.get_cybersource_client", return_value=mock_client)

    with pytest.raises(ApiException):
        verify_user_with_exports(user, run)
