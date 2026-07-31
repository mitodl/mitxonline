"""Service-to-service B2B serializers.

TEMPORARY -- delete alongside b2b/views/v0/service.py when org-manager status
becomes visible in Keycloak (mitodl/hq#10594).
"""

from rest_framework import serializers


class OrganizationManagerCheckSerializer(serializers.Serializer):
    """Response shape for the org-manager check."""

    is_manager = serializers.BooleanField(
        help_text="True if the user manages the organization.",
    )
