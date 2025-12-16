import requests

from digital_credential.constants import (
    DIGITAL_CREDENTIAL_STATUS_PATH,
    DIGITAL_CREDENTIAL_VERIFY_PATH,
)
from digital_credential.utils import create_verify_payload, dc_url


def verify_credential(credential_id):
    """Verifies a verifiableCredential and returns a verificationResult in the response body."""
    payload = create_verify_payload(credential_id)
    response = requests.post(
        dc_url(DIGITAL_CREDENTIAL_VERIFY_PATH), data=payload, timeout=10
    )
    return response.json()


def revoke_credential(credential_id, tenant_name, tenant_token):
    """Revoke a previously issued credential"""
    response = requests.post(
        dc_url(DIGITAL_CREDENTIAL_STATUS_PATH),
        headers={"Authorization": f"Bearer {tenant_token}"},
        json={
            "credentialId": credential_id,
            "credentialStatus": [
                {"type": "BitstringStatusListCredential", "status": "revoked"}
            ],
        },
        timeout=10,
    )
    return response.json()
