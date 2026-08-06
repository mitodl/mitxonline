"""CyberSource export compliance helpers."""

from __future__ import annotations

import json
import logging
from collections import namedtuple
from dataclasses import dataclass
from datetime import timedelta
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
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured, ObjectDoesNotExist
from django.db.models import Q
from mitol.common.utils.datetime import now_in_utc
from nacl.encoding import Base64Encoder
from nacl.public import PublicKey, SealedBox

from compliance.exceptions import ExportComplianceDataError
from compliance.models import ExportComplianceLog

log = logging.getLogger(__name__)

ISO_3166_2_PART_COUNT = 2
RECENT_EXPORT_COMPLIANCE_CHECK_WINDOW = timedelta(hours=24)

DecryptedExportComplianceLog = namedtuple(  # noqa: PYI024
    "DecryptedExportComplianceLog", ["request", "response"]
)


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
        return self.decision in ExportComplianceLog.ACCEPTED_DECISIONS


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


# Maps CyberSource bill-to field names to the profile field names an API
# consumer should show the user as missing.
BILL_TO_FIELD_TO_PROFILE_FIELD = {
    "first_name": "first_name",
    "last_name": "last_name",
    "email": "email",
    "address1": "street_address_1",
    "locality": "city",
    "country": "country",
    "administrative_area": "state",
    "postal_code": "postal_code",
}


def _missing_bill_to_fields(bill_to: dict[str, str]) -> list[str]:
    """Return the CyberSource bill-to field names missing from the given data."""
    missing_fields = []

    if not bill_to.get("first_name"):
        missing_fields.append("first_name")
    if not bill_to.get("last_name"):
        missing_fields.append("last_name")

    required_fields = ["address1", "locality", "country", "email"]
    if bill_to.get("country") in {"US", "CA"}:
        required_fields.extend(["administrative_area", "postal_code"])

    missing_fields.extend(field for field in required_fields if not bill_to.get(field))

    return missing_fields


def _validate_bill_to_fields(user, bill_to: dict[str, str]) -> None:
    """Raise a clear error when required CyberSource bill-to fields are missing."""
    missing_fields = _missing_bill_to_fields(bill_to)
    if missing_fields:
        raise ExportComplianceDataError(user, missing_fields)


def _build_bill_to(user) -> dict[str, str]:
    """Build the CyberSource bill-to fields from a user's legal address."""
    try:
        legal_address = user.legal_address
    except ObjectDoesNotExist:
        legal_address = None

    bill_to = {
        "email": user.email,
    }

    if legal_address and legal_address.first_name:
        bill_to["first_name"] = legal_address.first_name
    if legal_address and legal_address.last_name:
        bill_to["last_name"] = legal_address.last_name
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

    return bill_to


def get_missing_export_compliance_fields(user) -> list[str]:
    """Return the profile field names required for an export compliance check that are missing."""
    bill_to = _build_bill_to(user)
    missing_bill_to_fields = _missing_bill_to_fields(bill_to)
    return sorted(
        {BILL_TO_FIELD_TO_PROFILE_FIELD[field] for field in missing_bill_to_fields}
    )


def _build_export_payload(user) -> Any:
    """Build the CyberSource export compliance REST request payload."""
    bill_to = _build_bill_to(user)
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


def _get_raw_response_text(response: Any) -> str:
    """Return the raw wire-format text of a CyberSource REST response."""
    if isinstance(response, tuple) and len(response) > 2 and response[2]:  # noqa: PLR2004
        raw = response[2]
        return raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)

    payload = _get_response_payload(response)
    if hasattr(payload, "to_dict"):
        return json.dumps(payload.to_dict())
    if isinstance(payload, dict):
        return json.dumps(payload)
    return str(payload)


def get_encryption_public_key() -> PublicKey:
    """Return the public key used to encrypt cached export compliance data."""
    key = _require_setting("CYBERSOURCE_INQUIRY_LOG_NACL_ENCRYPTION_KEY")
    return PublicKey(key, encoder=Base64Encoder)


def log_export_compliance_check(
    user, run, request_payload: str, response: Any, result: ExportComplianceResult
) -> ExportComplianceLog:
    """Encrypt and store a CyberSource export compliance request/response for a user+run."""
    box = SealedBox(get_encryption_public_key())
    encrypted_request = box.encrypt(
        request_payload.encode("utf-8"), encoder=Base64Encoder
    ).decode("ascii")
    encrypted_response = box.encrypt(
        _get_raw_response_text(response).encode("utf-8"), encoder=Base64Encoder
    ).decode("ascii")

    return ExportComplianceLog.objects.create(
        user=user,
        courseware_object=run,
        decision=result.decision or "",
        reason_code="" if result.reason_code is None else str(result.reason_code),
        request_id=result.request_id or "",
        encrypted_request=encrypted_request,
        encrypted_response=encrypted_response,
    )


def get_latest_export_compliance_log(user, run) -> ExportComplianceLog | None:
    """
    Return the most recent export compliance log for a user that either
    matches the given courseware object, was created within the last 24
    hours (regardless of courseware object), or represents a prior failed
    check for this user (regardless of age or courseware object), if any.
    """
    cutoff = now_in_utc() - RECENT_EXPORT_COMPLIANCE_CHECK_WINDOW
    return (
        ExportComplianceLog.objects.filter(user=user)
        .filter(
            Q(
                courseware_content_type=ContentType.objects.get_for_model(run),
                courseware_object_id=run.id,
            )
            | Q(created_on__gte=cutoff)
            | ~Q(decision__in=ExportComplianceLog.ACCEPTED_DECISIONS)
        )
        .order_by("-created_on")
        .first()
    )


def decrypt_export_compliance_log(
    export_compliance_log: ExportComplianceLog, private_key
) -> DecryptedExportComplianceLog:
    """Decrypt a stored export compliance log given its matching NaCl private key."""
    box = SealedBox(private_key)

    decrypted_request = box.decrypt(
        export_compliance_log.encrypted_request, encoder=Base64Encoder
    ).decode("utf-8")
    decrypted_response = box.decrypt(
        export_compliance_log.encrypted_response, encoder=Base64Encoder
    ).decode("utf-8")

    return DecryptedExportComplianceLog(decrypted_request, decrypted_response)


def verify_user_with_exports(user, run) -> ExportComplianceResult:
    """
    Verify a user against CyberSource export compliance services for a given
    CourseRun or Program, reusing any cached result (accepted or failed)
    for the same courseware object, from the last 24 hours, or representing
    a prior failed check for this user.
    """
    cached_log = get_latest_export_compliance_log(user, run)
    if cached_log is not None:
        return ExportComplianceResult(
            decision=cached_log.decision,
            reason_code=cached_log.reason_code,
            request_id=cached_log.request_id,
            raw=None,
        )

    client = get_cybersource_client()
    request_payload = _serialize_export_payload(_build_export_payload(user))

    log.info(
        "Running CyberSource export compliance check for user=%s run=%s",
        user.id,
        run.id,
    )
    response = client.validate_export_compliance(request_payload)

    result = ExportComplianceResult(
        decision=_get_response_value(response, "status"),
        reason_code=_get_reason_code(response),
        request_id=_get_response_value(response, "id"),
        raw=response,
    )

    log_export_compliance_check(user, run, request_payload, response, result)

    return result
