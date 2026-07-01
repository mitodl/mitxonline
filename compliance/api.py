"""CyberSource export compliance helpers."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from CyberSource.api.verification_api import VerificationApi
from CyberSource.models.riskv1exportcomplianceinquiries_order_information import (
    Riskv1exportcomplianceinquiriesOrderInformation,
)
from CyberSource.models.riskv1exportcomplianceinquiries_order_information_bill_to import (
    Riskv1exportcomplianceinquiriesOrderInformationBillTo,
)
from CyberSource.models.riskv1liststypeentries_client_reference_information import (
    Riskv1liststypeentriesClientReferenceInformation,
)
from CyberSource.models.validate_export_compliance_request import (
    ValidateExportComplianceRequest,
)
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ObjectDoesNotExist

from compliance.exceptions import ExportComplianceDataError

log = logging.getLogger(__name__)

ISO_3166_2_PART_COUNT = 2


@dataclass(frozen=True)
class ExportComplianceResult:
    """Normalized export compliance response."""

    decision: str | None
    reason_code: str | int | None
    request_id: str | None
    raw: Any

    @property
    def accepted(self) -> bool:
        """Return True when CyberSource accepted the export check."""
        return self.decision in {"ACCEPT", "COMPLETED"}


def _require_setting(name: str) -> str:
    """Return a non-empty setting value or raise an error."""
    value = getattr(settings, name, None)
    if not value:
        message = f"{name} must be configured for export checks"
        raise ImproperlyConfigured(message)
    return value


def _get_cybersource_configuration() -> dict[str, str | int]:
    """Return REST client configuration for CyberSource export checks."""
    return {
        "authentication_type": "HTTP_SIGNATURE",
        "merchantid": _require_setting("MITOL_PAYMENT_GATEWAY_CYBERSOURCE_MERCHANT_ID"),
        "merchant_keyid": _require_setting(
            "MITOL_PAYMENT_GATEWAY_CYBERSOURCE_MERCHANT_SECRET_KEY_ID"
        ),
        "merchant_secretkey": _require_setting(
            "MITOL_PAYMENT_GATEWAY_CYBERSOURCE_MERCHANT_SECRET"
        ),
        "run_environment": _require_setting(
            "MITOL_PAYMENT_GATEWAY_CYBERSOURCE_REST_API_ENVIRONMENT"
        ),
        "timeout": 1000,
    }


def _split_user_name(user) -> tuple[str, str]:
    """Split a user's display name into first/last values."""
    full_name = (user.name or "").strip()
    if not full_name:
        return ("", "")

    name_parts = full_name.split(maxsplit=1)
    if len(name_parts) == 1:
        return (name_parts[0], "")

    return (name_parts[0], name_parts[1])


def _normalize_administrative_area(
    country: str | None, state: str | None
) -> str | None:
    """Normalize ISO-3166-2 style subdivision values for CyberSource bill-to data."""
    if not state:
        return None

    normalized_country = (country or "").strip().upper()
    normalized_state = state.strip()
    subdivision_parts = normalized_state.split("-", maxsplit=1)

    if (
        normalized_country
        and len(subdivision_parts) == ISO_3166_2_PART_COUNT
        and subdivision_parts[0].upper() == normalized_country
        and subdivision_parts[1]
    ):
        return subdivision_parts[1]

    return normalized_state


def _validate_bill_to_fields(user, bill_to: dict[str, str]) -> None:
    """Raise a clear error when required CyberSource bill-to fields are missing."""
    missing_fields = []

    if not bill_to.get("first_name"):
        missing_fields.append("first_name")
    if not bill_to.get("last_name"):
        missing_fields.append("last_name")

    required_fields = ["address1", "locality", "country", "email"]
    if bill_to.get("country") in {"US", "CA"}:
        required_fields.extend(["administrative_area", "postal_code"])

    missing_fields.extend(field for field in required_fields if not bill_to.get(field))

    if missing_fields:
        raise ExportComplianceDataError(user, missing_fields)


def _build_export_payload(user) -> Any:
    """Build the CyberSource export compliance REST request payload."""
    try:
        legal_address = user.legal_address
    except ObjectDoesNotExist:
        legal_address = None
    first_name, last_name = _split_user_name(user)

    bill_to = {
        "first_name": first_name,
        "last_name": last_name,
        "email": user.email,
    }

    if legal_address and legal_address.country:
        bill_to["country"] = legal_address.country
    if legal_address and legal_address.street_address_1:
        bill_to["address1"] = legal_address.street_address_1
    if legal_address and legal_address.street_address_2:
        bill_to["address2"] = legal_address.street_address_2
    if legal_address and legal_address.city:
        bill_to["locality"] = legal_address.city
    if legal_address and legal_address.state:
        bill_to["administrative_area"] = _normalize_administrative_area(
            legal_address.country,
            legal_address.state,
        )
    if legal_address and legal_address.postal_code:
        bill_to["postal_code"] = legal_address.postal_code

    _validate_bill_to_fields(user, bill_to)

    return ValidateExportComplianceRequest(
        client_reference_information=Riskv1liststypeentriesClientReferenceInformation(
            code=str(uuid4())
        ),
        order_information=Riskv1exportcomplianceinquiriesOrderInformation(
            bill_to=Riskv1exportcomplianceinquiriesOrderInformationBillTo(
                **{
                    key: value
                    for key, value in bill_to.items()
                    if value not in [None, ""]
                }
            )
        ),
    )


def _remove_none_values(value: Any) -> Any:
    """Recursively remove None values from SDK payload data."""
    if isinstance(value, dict):
        return {
            key: _remove_none_values(item)
            for key, item in value.items()
            if item is not None
        }
    if isinstance(value, list):
        return [_remove_none_values(item) for item in value if item is not None]
    return value


def _serialize_export_payload(payload: Any) -> str:
    """Serialize a CyberSource payload to the JSON string expected by this SDK build."""
    return json.dumps(_remove_none_values(payload.to_dict()))


def _get_response_payload(response: Any) -> Any:
    """Return the response body object from SDK return values."""
    if isinstance(response, tuple) and response:
        return response[0]
    return response


def _get_response_value(response: Any, *names: str) -> Any:
    """Read a value from an SDK response object or dict using any provided name."""
    payload = _get_response_payload(response)

    if isinstance(payload, dict):
        for name in names:
            if name in payload:
                return payload[name]
        return None

    for name in names:
        value = getattr(payload, name, None)
        if value is not None:
            return value

    return None


def get_cybersource_client():
    """Create an authenticated REST client for CyberSource export checks."""
    return VerificationApi(_get_cybersource_configuration())


def _get_reason_code(response) -> str | None:
    """Extract the most useful reason code from a REST response."""
    export_info = _get_response_value(
        response,
        "export_compliance_information",
        "exportComplianceInformation",
    )
    info_codes = _get_response_value(export_info, "info_codes", "infoCodes") or []
    if info_codes:
        return ",".join(info_codes)

    error_info = _get_response_value(response, "error_information", "errorInformation")
    return _get_response_value(error_info, "reason") or _get_response_value(
        response, "message"
    )


def verify_user_with_exports(user) -> ExportComplianceResult:
    """Verify a user against CyberSource export compliance services."""
    client = get_cybersource_client()
    payload = _serialize_export_payload(_build_export_payload(user))

    log.info("Running CyberSource export compliance check for user=%s", user.id)
    response = client.validate_export_compliance(payload)

    return ExportComplianceResult(
        decision=_get_response_value(response, "status"),
        reason_code=_get_reason_code(response),
        request_id=_get_response_value(response, "id"),
        raw=response,
    )
