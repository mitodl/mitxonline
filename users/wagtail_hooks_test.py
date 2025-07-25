"""Tests for users Wagtail hooks."""

import pytest
from django.contrib.auth import get_user_model
from wagtail.users.views.users import IndexView

User = get_user_model()


class TestWagtailUserOrdering:
    """Test custom Wagtail user ordering hook."""

    def test_user_index_view_ordering_uses_legal_address_fields(self):
        """
        Test that the users IndexView orders by legal_address fields.
        
        This ensures our monkey-patch fix for the FieldError is working correctly.
        The error occurred because our User model has first_name and last_name as
        properties that delegate to legal_address, but Wagtail's default ordering
        tried to order by the fields directly on the User model.
        """
        # Create a queryset
        queryset = User.objects.all()
        
        # Create an instance of IndexView
        view = IndexView()
        
        # The order_queryset method should work without raising a FieldError
        ordered_queryset = view.order_queryset(queryset)
        
        # Verify the ordering uses the correct database field paths
        ordering = ordered_queryset.query.order_by
        expected_ordering = ("legal_address__last_name", "legal_address__first_name")
        
        assert tuple(ordering) == expected_ordering
        
    def test_user_index_view_ordering_with_existing_users(self, user_factory):
        """Test that the ordering works with actual user data."""
        # Create test users with legal addresses
        user1 = user_factory.create()
        user1.legal_address.first_name = "Alice"
        user1.legal_address.last_name = "Smith"
        user1.legal_address.save()
        
        user2 = user_factory.create()
        user2.legal_address.first_name = "Bob"
        user2.legal_address.last_name = "Johnson"
        user2.legal_address.save()
        
        # Create a queryset
        queryset = User.objects.filter(id__in=[user1.id, user2.id])
        
        # Create an instance of IndexView
        view = IndexView()
        
        # The order_queryset method should work and return users in alphabetical order by last name
        ordered_queryset = view.order_queryset(queryset)
        
        # Execute the query and verify the ordering
        ordered_users = list(ordered_queryset)
        
        # Johnson should come before Smith alphabetically
        assert ordered_users[0].legal_address.last_name == "Johnson"
        assert ordered_users[1].legal_address.last_name == "Smith"