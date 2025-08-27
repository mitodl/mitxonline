"""Custom permissions"""

from rest_framework import permissions


class UserIsOwnerPermission(permissions.BasePermission):
    """Determines if the user owns the object"""

    def has_object_permission(self, request, view, obj):
        """
        Returns True if the requesting user is the owner of the object as
        determined by the "owner_field" property on the view (defaults to "user")
        """
        owner_field = getattr(view, "owner_field", None)

        if owner_field is None:  # noqa: SIM108
            # if no owner_field is specified, the object itself is compared
            owner = obj
        else:
            # otherwise we lookup the owner by the specified field
            owner = getattr(obj, owner_field)

        return owner == request.user


class IsAdminOrReadOnly(permissions.IsAdminUser):
    """
    Allows full access to admins, but read-only access to authenticated users.
    """

    def has_permission(self, request, view):
        """Return True if the user is an admin, or if the user is authenticated and making a safe request."""
        if request.user and request.user.is_staff:
            return True
        return (
            request.method in permissions.SAFE_METHODS
            and request.user
            and request.user.is_authenticated
        )
