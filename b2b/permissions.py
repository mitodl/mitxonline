"""B2B permissions for organization manager dashboard."""

from rest_framework import permissions

from .models import is_organization_manager


class IsOrganizationManager(permissions.BasePermission):
    """
    Custom permission to only allow organization managers to access
    their organization's data.
    """

    def has_permission(self, request, view):
        """
        Check if the user has permission to access the view.

        The user must be authenticated and be a manager of the organization
        specified in the URL parameters.
        """
        if not request.user or not request.user.is_authenticated:
            return False

        # Get org_id from URL kwargs
        org_id = view.kwargs.get("org_id")
        if not org_id:
            return False

        return is_organization_manager(request.user, org_id)

    def has_object_permission(self, request, view, obj):
        """
        Check if the user has permission to access a specific object.

        For contract-related objects, ensure the contract belongs to
        an organization that the user manages.
        """
        if not request.user or not request.user.is_authenticated:
            return False

        org_id = view.kwargs.get("org_id")
        if not org_id:
            return False

        # Check if user is manager of the organization
        if not is_organization_manager(request.user, org_id):
            return False

        # If the object has an organization relation, verify it matches
        if hasattr(obj, "organization_id"):
            return obj.organization_id == int(org_id)
        elif hasattr(obj, "organization"):
            return obj.organization.id == int(org_id)
        elif hasattr(obj, "b2b_contract"):
            # For course runs and enrollments
            return obj.b2b_contract.organization_id == int(org_id)
        elif hasattr(obj, "run") and hasattr(obj.run, "b2b_contract"):
            # For enrollments via course run
            return obj.run.b2b_contract.organization_id == int(org_id)

        return True
