from digital_credential.utils import dc_url
from digital_credential.constants import DIGITAL_CREDENTIAL_VERIFY_PATH, DIGITAL_CREDENTIAL_STATUS_PATH, \
    VERIFY_REQUEST_BODY

import requests



def verify_credential(credential):
    """Verifies a verifiableCredential and returns a verificationResult in the response body."""

    response = requests.post(
        dc_url(DIGITAL_CREDENTIAL_VERIFY_PATH), data=VERIFY_REQUEST_BODY
    )
    return response.json()

def revoke_credential(credential_id, tenant_name, tenant_token):
    """Revoke a previously issued credential"""
    response = requests.post(
        dc_url(DIGITAL_CREDENTIAL_STATUS_PATH),
        headers={"Authorization": f"Bearer {tenant_token}"},
        json={
            "credentialId": credential_id,
            "credentialStatus": [{
                "type": "BitstringStatusListCredential",
                "status": "revoked"
            }]
        }
    )
    return response.json()
