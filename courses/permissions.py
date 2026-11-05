"""Specialized DRF permission classes for courses"""

from rest_framework.permissions import BasePermission


class IsEtlUser(BasePermission):
    """Allow only is_etl flagged users through."""

    message = "Invalid user."

    def has_permission(self, request, view):  # noqa: ARG002
        """Check the user's is_etl flag."""

        return (
            request.user
            and not request.user.is_anonymous
            and (request.user.is_etl or request.user.is_superuser)
        )
