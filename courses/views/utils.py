"""
View utility functions.

These were in the views themselves, and have been moved so they're more intuitive
to import elsewhere.
"""

from django.shortcuts import get_object_or_404

from main.pagination import Pagination

__all__ = ["Pagination", "ReadableIdLookupMixin"]


class ReadableIdLookupMixin:
    """
    Mixin to support lookup by either integer pk or readable_id string.
    """

    def get_object(self):
        """
        Returns the object the view is displaying.
        Supports lookup by either integer pk or readable_id string.
        """
        queryset = self.filter_queryset(self.get_queryset())
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        identifier = self.kwargs[lookup_url_kwarg]

        filter_kwargs = (
            {"pk": int(identifier)}
            if identifier.isdigit()
            else {"readable_id": identifier}
        )

        obj = get_object_or_404(queryset, **filter_kwargs)
        self.check_object_permissions(self.request, obj)
        return obj
