from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
import requests

from .api import revoke_credential, verify_credential



@api_view(["POST"])
@permission_classes([AllowAny])
def credential_verify_view(request):
    """
    Function-based API view to verify a credential
    """
    credential_id = request.data.get("credentialId")
    try:
        result = verify_credential(credential_id)
        return Response(result)
    except requests.RequestException as e:
        return Response({"error": str(e)}, status=status.HTTP_502_BAD_GATEWAY)


@api_view(["POST"])
@permission_classes([AllowAny])
def credential_revoke_view(request):
    """
    Function-based API view to revoke a credential by calling revoke_credential from api.py.
    Expects credentialId, tenant_name, and tenant_token in the request data.
    """
    credential_id = request.data.get("credentialId")
    tenant_name = request.data.get("tenant_name")
    tenant_token = request.data.get("tenant_token")
    if not all([credential_id, tenant_name, tenant_token]):
        return Response({"error": "Missing required fields: credentialId, tenant_name, tenant_token"}, status=status.HTTP_400_BAD_REQUEST)
    try:
        result = revoke_credential(credential_id, tenant_name, tenant_token)
        return Response(result)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_502_BAD_GATEWAY)
