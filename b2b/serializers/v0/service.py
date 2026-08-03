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


class ServiceDetailErrorSerializer(serializers.Serializer):
    """Response shape for the 400 error responses below.

    Same shape as b2b.serializers.v0.manager.DetailErrorSerializer, but
    duplicated rather than imported (and distinctly named, since
    drf-spectacular keys its component registry on class identity, not
    structural equality -- reusing the same name for a different class
    produces a "components with identical names" warning and an
    unpredictable schema) so this module stays self-contained and its
    deletion remains a plain file removal (see the module docstring in
    b2b/views/v0/service.py).
    """

    detail = serializers.CharField()
