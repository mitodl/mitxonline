DIGITAL_CREDENTIAL_ISSUE_PATH = "credentials/issue/"
DIGITAL_CREDENTIAL_STATUS_PATH = "credentials/status/"
DIGITAL_CREDENTIAL_VERIFY_PATH = "credentials/verify/"
DIGITAL_CREDENTIAL_ISSUER = "MIT Learn"

CREDENTIAL_TYPE = "EnvelopedVerifiableCredential"

VERIFY_REQUEST_BODY = {
"verifiableCredential": {
        "@context": [
            "www.w3.org",
            "www.w3.org"
        ],
        "id": "credential_id",
        "type": [
            "VerifiableCredential",
            "UniversityDegreeCredential"
        ],
        "issuer": DIGITAL_CREDENTIAL_ISSUER,
        "issuanceDate": "2010-01-01T19:23:24Z",
        "credentialSubject": {},
        "proof": {
            "type": "",
            "created": "",
            "proofPurpose": "assertionMethod",
            "verificationMethod": "",
        }
    },
    "verifyStatus": True,
    "fetchRemoteContexts": False
}
