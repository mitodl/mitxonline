"""Custom Wagtail hooks for users app."""

from wagtail import hooks
from wagtail.users.views.users import IndexView


# Store the original order_queryset method
_original_order_queryset = IndexView.order_queryset


def custom_order_queryset(self, queryset):
    """
    Custom ordering method that uses legal_address fields instead of direct user fields.
    
    This fixes the FieldError that occurs because our User model has first_name and last_name
    as properties that delegate to legal_address.first_name and legal_address.last_name,
    but Wagtail's default ordering tries to order by the fields directly.
    """
    return queryset.order_by("legal_address__last_name", "legal_address__first_name")


# Monkey-patch the IndexView to use our custom ordering
IndexView.order_queryset = custom_order_queryset