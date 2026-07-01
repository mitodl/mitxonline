"""CyberSource export compliance helpers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Any
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ObjectDoesNotExist

try:
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
except ModuleNotFoundError as exc:
    VerificationApi = None
    Riskv1exportcomplianceinquiriesOrderInformation = None
    Riskv1exportcomplianceinquiriesOrderInformationBillTo = None
    Riskv1liststypeentriesClientReferenceInformation = None
    ValidateExportComplianceRequest = None
    _CYBERSOURCE_IMPORT_ERROR = exc
else:
    _CYBERSOURCE_IMPORT_ERROR = None

log = logging.getLogger(__name__)


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


@dataclass(frozen=True)
class _CyberSourceSdk:
    """Official CyberSource REST SDK classes used for export compliance."""

    verification_api_class: Any
    order_information_class: Any
    bill_to_class: Any
    client_reference_information_class: Any
    validate_export_compliance_request_class: Any


def _require_setting(name: str) -> str:
    """Return a non-empty setting value or raise an error."""
    value = getattr(settings, name, None)
    if not value:
        message = f"{name} must be configured for export checks"
        raise ImproperlyConfigured(message)
    return value


@lru_cache(maxsize=1)
def _load_cybersource_sdk() -> _CyberSourceSdk:
    """Load the official CyberSource REST SDK classes used by this module."""
    if _CYBERSOURCE_IMPORT_ERROR is not None:
        message = "CyberSource SDK must be installed to use export compliance checks"
        raise ImproperlyConfigured(message) from _CYBERSOURCE_IMPORT_ERROR

    return _CyberSourceSdk(
        verification_api_class=VerificationApi,
        order_information_class=Riskv1exportcomplianceinquiriesOrderInformation,
        bill_to_class=Riskv1exportcomplianceinquiriesOrderInformationBillTo,
        client_reference_information_class=Riskv1liststypeentriesClientReferenceInformation,
        validate_export_compliance_request_class=ValidateExportComplianceRequest,
    )


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


def _get_user_legal_address(user):
    """Return the user's legal address if one exists."""
    try:
        return user.legal_address
    except ObjectDoesNotExist:
        return None


def _split_user_name(user) -> tuple[str, str]:
    """Split a user's display name into first/last values."""
    full_name = (user.name or "").strip()
    if not full_name:
        return ("", "")

    name_parts = full_name.split(maxsplit=1)
    if len(name_parts) == 1:
        return (name_parts[0], "")

    return (name_parts[0], name_parts[1])


def _build_export_payload(user) -> Any:
    """Build the CyberSource export compliance REST request payload."""
    sdk = _load_cybersource_sdk()

    legal_address = _get_user_legal_address(user)
    first_name, last_name = _split_user_name(user)

    bill_to = {
        "first_name": first_name,
        "last_name": last_name,
        "email": user.email,
    }

    if legal_address and legal_address.country:
        bill_to["country"] = legal_address.country
    if legal_address and legal_address.state:
        bill_to["administrative_area"] = legal_address.state

    return sdk.validate_export_compliance_request_class(
        client_reference_information=sdk.client_reference_information_class(
            code=str(uuid4())
        ),
        order_information=sdk.order_information_class(
            bill_to=sdk.bill_to_class(
                **{
                    key: value
                    for key, value in bill_to.items()
                    if value not in [None, ""]
                }
            )
        ),
    )


def get_cybersource_client():
    """Create an authenticated REST client for CyberSource export checks."""
    sdk = _load_cybersource_sdk()

    return sdk.verification_api_class(_get_cybersource_configuration())


def _get_reason_code(response) -> str | None:
    """Extract the most useful reason code from a REST response."""
    export_info = getattr(response, "export_compliance_information", None)
    info_codes = getattr(export_info, "info_codes", None) or []
    if info_codes:
        return ",".join(info_codes)

    error_info = getattr(response, "error_information", None)
    return getattr(error_info, "reason", None) or getattr(response, "message", None)


def verify_user_with_exports(user) -> ExportComplianceResult:
    """Verify a user against CyberSource export compliance services."""
    client = get_cybersource_client()
    payload = _build_export_payload(user)

    log.info("Running CyberSource export compliance check for user=%s", user.id)
    response = client.validate_export_compliance(payload)

    return ExportComplianceResult(
        decision=getattr(response, "status", None),
        reason_code=_get_reason_code(response),
        request_id=getattr(response, "id", None),
        raw=response,
    )
