import logging

import requests
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import serializers
from drf_spectacular.utils import extend_schema

from .api import revoke_credential, verify_credential


class CredentialSerializer(serializers.Serializer):
    credentialId = serializers.CharField()
    tenant_name = serializers.CharField()
    tenant_token = serializers.CharField()


@extend_schema(
    description="Verifies credential using ....",
    responses={200: CredentialSerializer}
)
@api_view(["POST"])
@permission_classes((IsAuthenticated,))
def credential_verify_view(request):
    """
    Function-based API view to verify a credential
    """
    credential_id = request.data.get("credentialId")
    try:
        result = verify_credential(credential_id)
        return Response(result)
    except requests.RequestException:
        logging.exception("Error verifying credential")
        return Response(
            {"error": "An internal error has occurred."},
            status=status.HTTP_502_BAD_GATEWAY,
        )


@extend_schema(
    description="Revokes credential using credential id",
    responses={200: CredentialSerializer}
)
@api_view(["POST"])
@permission_classes((IsAuthenticated,))
def credential_revoke_view(request):
    """
    Function-based API view to revoke a credential by calling revoke_credential from api.py.
    """
    credential_id = request.data.get("credentialId")
    try:
        result = revoke_credential(credential_id)
        return Response(result)
    except requests.RequestException:
        logging.exception("Error revoking credential")
        return Response(
            {"error": "An internal error has occurred."},
            status=status.HTTP_502_BAD_GATEWAY,
        )
