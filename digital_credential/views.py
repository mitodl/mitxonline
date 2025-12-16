from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import requests

from digital_credential.utils import dc_url

DIGITAL_CREDENTAIL_STATUS_PATH = "credentails/status/"

class CredentialPresentView(APIView):
    """
    API endpoint to proxy GET /credentials/present/<credential_id> to the digitalcredentials/issuer-coordinator service.
    """
    def get(self, request, credential_id):
        try:
            resp = requests.get(dc_url(DIGITAL_CREDENTAIL_STATUS_PATH))
            return Response(resp.json(), status=resp.status_code)
        except requests.RequestException as e:
            return Response({"error": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

class CredentialRevokeView(APIView):
    """
    API endpoint to proxy POST /credentials/revoke to the digitalcredentials/issuer-coordinator service.
    """
    def post(self, request):
        try:
            payload = {
                "credentialId": request.data.get("credentialId"),
                "credentialStatus": [{
                    "type": "BitstringStatusListCredential",
                    "status": "revoked"
                }]
            }
            resp = requests.post(dc_url(DIGITAL_CREDENTAIL_STATUS_PATH), json=payload)
            return Response(resp.json(), status=resp.status_code)
        except requests.RequestException as e:
            return Response({"error": str(e)}, status=status.HTTP_502_BAD_GATEWAY)


class CredentialVerifyView(APIView):
    """
    API endpoint to proxy POST /credentials/verify to the digitalcredentials/issuer-coordinator service.
    """
    def post(self, request):
        try:
            resp = requests.post(external_url, json=request.data)
            return Response(resp.json(), status=resp.status_code)
        except requests.RequestException as e:
            return Response({"error": str(e)}, status=status.HTTP_502_BAD_GATEWAY)
