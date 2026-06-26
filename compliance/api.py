"""CyberSource export compliance helpers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ObjectDoesNotExist

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
        return self.decision == "ACCEPT"


def _require_setting(name: str) -> str:
    """Return a non-empty setting value or raise an error."""
    value = getattr(settings, name, None)
    if not value:
        raise ImproperlyConfigured(f"{name} must be configured for export checks")
    return value


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


def _build_export_payload(user) -> dict[str, Any]:
    """Build the CyberSource export compliance request payload."""
    legal_address = _get_user_legal_address(user)
    first_name, last_name = _split_user_name(user)

    bill_to = {
        "firstName": first_name,
        "lastName": last_name,
        "email": user.email,
    }

    if legal_address and legal_address.country:
        bill_to["country"] = legal_address.country
    if legal_address and legal_address.state:
        bill_to["administrativeArea"] = legal_address.state

    return {
        "merchantID": settings.CYBERSOURCE_MERCHANT_ID,
        "merchantReferenceCode": str(uuid4()),
        "exportService": {
            "run": "true" if settings.CYBERSOURCE_EXPORT_SERVICE_RUN else "false"
        },
        "billTo": {
            key: value for key, value in bill_to.items() if value not in [None, ""]
        },
    }


def get_cybersource_client():
    """Create an authenticated SOAP client for CyberSource export checks."""
    wsdl_url = _require_setting("CYBERSOURCE_WSDL_URL")
    merchant_id = _require_setting("CYBERSOURCE_MERCHANT_ID")
    transaction_key = _require_setting("CYBERSOURCE_TRANSACTION_KEY")

    try:
        from zeep import Client
        from zeep.wsse.username import UsernameToken
    except ModuleNotFoundError as exc:
        raise ImproperlyConfigured(
            "zeep must be installed to use CyberSource export compliance checks"
        ) from exc

    return Client(
        wsdl=wsdl_url,
        wsse=UsernameToken(merchant_id, transaction_key),
    )


def verify_user_with_exports(user) -> ExportComplianceResult:
    """Verify a user against CyberSource export compliance services."""
    client = get_cybersource_client()
    payload = _build_export_payload(user)

    log.info("Running CyberSource export compliance check for user=%s", user.id)
    response = client.service.runTransaction(**payload)

    return ExportComplianceResult(
        decision=getattr(response, "decision", None),
        reason_code=getattr(response, "reasonCode", None),
        request_id=getattr(response, "requestID", None),
        raw=response,
    )
