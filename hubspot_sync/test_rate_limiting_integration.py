"""Tests for rate limiting integration in API and tasks"""

from unittest.mock import Mock, patch

import pytest
from django.conf import settings
from django.test import override_settings
from hubspot.crm.objects import ApiException
from mitol.hubspot_api.exceptions import TooManyRequestsException

from hubspot_sync import api
from hubspot_sync.tasks import sync_contact_with_hubspot, sync_failed_contacts
from users.factories import UserFactory

pytestmark = [pytest.mark.django_db]


class TestAPIRateLimitingIntegration:
    """Test rate limiting integration in API functions."""

    @patch("hubspot_sync.api.wait_for_hubspot_rate_limit")
    @patch("hubspot_sync.api.upsert_object_request")
    @patch("hubspot_sync.api.make_contact_sync_message_from_user")
    def test_sync_contact_with_hubspot_applies_rate_limiting(
        self, mock_make_message, mock_upsert, mock_rate_limit
    ):
        """Test that sync_contact_with_hubspot applies rate limiting before API call."""
        user = UserFactory()
        mock_make_message.return_value = Mock()
        mock_result = Mock()
        mock_result.id = "hubspot_id_123"
        mock_upsert.return_value = mock_result

        result = api.sync_contact_with_hubspot(user)

        mock_rate_limit.assert_called_once_with()
        mock_upsert.assert_called_once()
        assert result == mock_result

    @patch("hubspot_sync.api.wait_for_hubspot_rate_limit")
    @patch("hubspot_sync.api.upsert_object_request")
    def test_sync_contact_with_hubspot_rate_limit_with_response_headers(
        self, mock_upsert, mock_rate_limit
    ):
        """Test that we could potentially pass response headers to rate limiter."""
        user = UserFactory()
        mock_result = Mock()
        mock_result.id = "hubspot_id_123"
        mock_upsert.return_value = mock_result

        api.sync_contact_with_hubspot(user)

        mock_rate_limit.assert_called_once_with()

    @patch("hubspot_sync.api.wait_for_hubspot_rate_limit")
    @patch("hubspot_sync.api.upsert_object_request")
    def test_sync_contact_with_hubspot_rate_limit_called_before_api(
        self, mock_upsert, mock_rate_limit
    ):
        """Test that rate limiting is called before the API request."""
        user = UserFactory()
        mock_upsert.side_effect = ApiException("Test error")

        with pytest.raises(ApiException):
            api.sync_contact_with_hubspot(user)

        mock_rate_limit.assert_called_once_with()


class TestTaskRateLimitingIntegration:
    """Test rate limiting integration in Celery tasks."""

    @patch("hubspot_sync.tasks.api.sync_contact_with_hubspot")
    @patch("hubspot_sync.tasks.User.objects.get")
    def test_sync_contact_with_hubspot_task(self, mock_get_user, mock_sync_contact):
        """Test that the task correctly calls the API function."""
        user = UserFactory()
        mock_get_user.return_value = user
        mock_result = Mock()
        mock_result.id = "hubspot_id_123"
        mock_sync_contact.return_value = mock_result

        result = sync_contact_with_hubspot(user.id)

        assert result == "hubspot_id_123"
        mock_get_user.assert_called_once_with(id=user.id)
        mock_sync_contact.assert_called_once_with(user)

    @patch("hubspot_sync.tasks.wait_for_hubspot_rate_limit")
    @patch("hubspot_sync.tasks.api.sync_contact_with_hubspot")
    @patch("hubspot_sync.tasks.User.objects.filter")
    def test_sync_failed_contacts_applies_rate_limiting(
        self, mock_filter, mock_sync_contact, mock_rate_limit
    ):
        """Test that sync_failed_contacts applies rate limiting for each contact."""
        users = [UserFactory(), UserFactory(), UserFactory()]
        mock_filter.return_value = users
        mock_sync_contact.return_value = Mock()

        result = sync_failed_contacts([u.id for u in users])

        assert mock_rate_limit.call_count == 3
        assert mock_sync_contact.call_count == 3
        assert result == []

    @patch("hubspot_sync.tasks.wait_for_hubspot_rate_limit")
    @patch("hubspot_sync.tasks.api.sync_contact_with_hubspot")
    @patch("hubspot_sync.tasks.User.objects.filter")
    def test_sync_failed_contacts_handles_exceptions(
        self, mock_filter, mock_sync_contact, mock_rate_limit
    ):
        """Test that sync_failed_contacts handles API exceptions and continues."""
        users = [UserFactory(), UserFactory(), UserFactory()]
        mock_filter.return_value = users

        mock_sync_contact.side_effect = [Mock(), ApiException("Rate limited"), Mock()]

        result = sync_failed_contacts([u.id for u in users])

        assert mock_rate_limit.call_count == 3
        assert mock_sync_contact.call_count == 3
        assert result == [users[1].id]

    @patch("hubspot_sync.tasks.wait_for_hubspot_rate_limit")
    @patch("hubspot_sync.tasks.api.sync_contact_with_hubspot")
    @patch("hubspot_sync.tasks.User.objects.filter")
    def test_sync_failed_contacts_rate_limiting_called_before_sync(
        self, mock_filter, mock_sync_contact, mock_rate_limit
    ):
        """Test that rate limiting is called before each sync operation."""
        users = [UserFactory()]
        mock_filter.return_value = users

        mock_sync_contact.side_effect = ApiException("Test error")

        result = sync_failed_contacts([users[0].id])

        mock_rate_limit.assert_called_once_with()
        assert result == [users[0].id]


class TestRateLimitingConfiguration:
    """Test rate limiting configuration and settings."""

    @override_settings(HUBSPOT_TASK_DELAY=200)
    @patch("hubspot_sync.rate_limiter.time.sleep")
    @patch("hubspot_sync.rate_limiter.time.time")
    def test_custom_task_delay_setting(self, mock_time, mock_sleep):
        """Test that custom HUBSPOT_TASK_DELAY setting is respected."""
        from hubspot_sync.rate_limiter import HubSpotRateLimiter

        mock_time.side_effect = [0, 0, 0]

        limiter = HubSpotRateLimiter()
        assert limiter.min_delay_ms == 200

        limiter.wait_for_rate_limit()

        mock_sleep.assert_called_once_with(0.2)

    @override_settings(HUBSPOT_AGGRESSIVE_RATE_LIMITING=False)
    def test_aggressive_rate_limiting_disabled(self):
        """Test behavior when aggressive rate limiting is disabled."""

        assert not settings.HUBSPOT_AGGRESSIVE_RATE_LIMITING


class TestRateLimitingErrorScenarios:
    """Test rate limiting behavior in error scenarios."""

    @patch("hubspot_sync.api.wait_for_hubspot_rate_limit")
    @patch("hubspot_sync.api.upsert_object_request")
    def test_rate_limiting_with_too_many_requests_exception(
        self, mock_upsert, mock_rate_limit
    ):
        """Test that rate limiting is still applied even when API raises TooManyRequestsException."""
        user = UserFactory()
        mock_upsert.side_effect = TooManyRequestsException("Rate limited")

        with pytest.raises(TooManyRequestsException):
            api.sync_contact_with_hubspot(user)

        mock_rate_limit.assert_called_once_with()

    @patch("hubspot_sync.api.wait_for_hubspot_rate_limit")
    @patch("hubspot_sync.api.upsert_object_request")
    def test_rate_limiting_with_api_exception(self, mock_upsert, mock_rate_limit):
        """Test that rate limiting is applied before API exceptions."""
        user = UserFactory()
        mock_upsert.side_effect = ApiException("General API error")

        with pytest.raises(ApiException):
            api.sync_contact_with_hubspot(user)

        mock_rate_limit.assert_called_once_with()

