"""Test openedx views"""

from unittest.mock import patch

import pytest
from django.shortcuts import reverse
from rest_framework import status
from rest_framework.test import APIClient

from courses.factories import CourseRunEnrollmentFactory, CourseRunFactory
from users.factories import UserFactory

pytestmark = [pytest.mark.django_db]

WEBHOOK_URL = "openedx-enrollment-webhook"
TEST_WEBHOOK_KEY = "test-webhook-secret-key"


@pytest.mark.parametrize(
    "route",
    [
        "openedx-private-oauth-complete",
        "openedx-private-oauth-complete-no-apisix",
    ],
)
def test_openedx_private_auth_complete_view(client, route):
    """Verify the openedx_private_auth_complete view returns a 200"""
    response = client.get(reverse(route))
    assert response.status_code == status.HTTP_200_OK


class TestEdxEnrollmentWebhook:
    """Tests for the edx_enrollment_webhook view"""

    @pytest.fixture
    def api_client(self):
        """Unauthenticated API client"""
        return APIClient()

    @pytest.fixture
    def webhook_payload(self):
        """Standard webhook payload"""
        return {
            "email": "instructor@example.com",
            "course_id": "course-v1:MITx+1.001x+2025_T1",
            "role": "instructor",
        }

    def _post_webhook(self, api_client, payload, token=TEST_WEBHOOK_KEY):
        """Helper to POST to the webhook with Bearer auth"""
        headers = {}
        if token is not None:
            headers["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        return api_client.post(
            reverse(WEBHOOK_URL),
            data=payload,
            format="json",
            **headers,
        )

    @pytest.mark.parametrize("role", ["instructor", "staff"])
    @patch("openedx.views.create_run_enrollments")
    def test_successful_enrollment(
        self, mock_create_enrollments, api_client, role, settings
    ):
        """Test successful enrollment of a user as auditor via webhook"""
        settings.OPENEDX_WEBHOOK_KEY = TEST_WEBHOOK_KEY
        user = UserFactory.create()
        course_run = CourseRunFactory.create()
        enrollment = CourseRunEnrollmentFactory.create(user=user, run=course_run)
        mock_create_enrollments.return_value = ([enrollment], True)

        payload = {
            "email": user.email,
            "course_id": course_run.courseware_id,
            "role": role,
        }
        response = self._post_webhook(api_client, payload)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["message"] == "Enrollment successful"
        assert response.data["enrollment_id"] == enrollment.id
        mock_create_enrollments.assert_called_once_with(
            user,
            [course_run],
            keep_failed_enrollments=True,
        )

    def test_missing_authorization_header(self, api_client, webhook_payload, settings):
        """Test request without Authorization header returns 401"""
        settings.OPENEDX_WEBHOOK_KEY = TEST_WEBHOOK_KEY
        response = api_client.post(
            reverse(WEBHOOK_URL),
            data=webhook_payload,
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_invalid_auth_scheme(self, api_client, webhook_payload, settings):
        """Test request with non-Bearer auth scheme returns 401"""
        settings.OPENEDX_WEBHOOK_KEY = TEST_WEBHOOK_KEY
        response = api_client.post(
            reverse(WEBHOOK_URL),
            data=webhook_payload,
            format="json",
            HTTP_AUTHORIZATION="Basic dXNlcjpwYXNz",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_wrong_token(self, api_client, webhook_payload, settings):
        """Test request with wrong Bearer token returns 403"""
        settings.OPENEDX_WEBHOOK_KEY = TEST_WEBHOOK_KEY
        response = self._post_webhook(api_client, webhook_payload, token="wrong-token")  # noqa: S106
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_webhook_key_not_configured(self, api_client, webhook_payload, settings):
        """Test returns 500 when OPENEDX_WEBHOOK_KEY is not set"""
        settings.OPENEDX_WEBHOOK_KEY = None
        response = self._post_webhook(api_client, webhook_payload)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "not configured" in response.data["error"]

    def test_missing_email(self, api_client, settings):
        """Test request missing email returns 400"""
        settings.OPENEDX_WEBHOOK_KEY = TEST_WEBHOOK_KEY
        payload = {"course_id": "course-v1:MITx+1.001x+2025_T1", "role": "staff"}
        response = self._post_webhook(api_client, payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_missing_course_id(self, api_client, settings):
        """Test request missing course_id returns 400"""
        settings.OPENEDX_WEBHOOK_KEY = TEST_WEBHOOK_KEY
        payload = {"email": "instructor@example.com", "role": "staff"}
        response = self._post_webhook(api_client, payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_user_not_found(self, api_client, settings):
        """Test returns 404 when the user email doesn't exist"""
        settings.OPENEDX_WEBHOOK_KEY = TEST_WEBHOOK_KEY
        course_run = CourseRunFactory.create()
        payload = {
            "email": "nonexistent@example.com",
            "course_id": course_run.courseware_id,
            "role": "instructor",
        }
        response = self._post_webhook(api_client, payload)
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.data["error"]

    def test_course_run_not_found(self, api_client, settings):
        """Test returns 404 when the course run doesn't exist"""
        settings.OPENEDX_WEBHOOK_KEY = TEST_WEBHOOK_KEY
        user = UserFactory.create()
        payload = {
            "email": user.email,
            "course_id": "course-v1:MITx+NONEXISTENT+2025_T1",
            "role": "instructor",
        }
        response = self._post_webhook(api_client, payload)
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.data["error"]

    @patch("openedx.views.create_run_enrollments")
    def test_enrollment_creation_exception(
        self, mock_create_enrollments, api_client, settings
    ):
        """Test returns 500 when enrollment creation raises an exception"""
        settings.OPENEDX_WEBHOOK_KEY = TEST_WEBHOOK_KEY
        user = UserFactory.create()
        course_run = CourseRunFactory.create()
        mock_create_enrollments.side_effect = Exception("Unexpected error")

        payload = {
            "email": user.email,
            "course_id": course_run.courseware_id,
            "role": "instructor",
        }
        response = self._post_webhook(api_client, payload)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Failed to create enrollment" in response.data["error"]

    @patch("openedx.views.create_run_enrollments")
    def test_enrollment_returns_empty(
        self, mock_create_enrollments, api_client, settings
    ):
        """Test returns 500 when enrollment creation returns empty list"""
        settings.OPENEDX_WEBHOOK_KEY = TEST_WEBHOOK_KEY
        user = UserFactory.create()
        course_run = CourseRunFactory.create()
        mock_create_enrollments.return_value = ([], True)

        payload = {
            "email": user.email,
            "course_id": course_run.courseware_id,
            "role": "instructor",
        }
        response = self._post_webhook(api_client, payload)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @patch("openedx.views.create_run_enrollments")
    def test_already_enrolled_user(self, mock_create_enrollments, api_client, settings):
        """Test that webhook succeeds for an already-enrolled user (idempotent)"""
        settings.OPENEDX_WEBHOOK_KEY = TEST_WEBHOOK_KEY
        user = UserFactory.create()
        course_run = CourseRunFactory.create()
        enrollment = CourseRunEnrollmentFactory.create(user=user, run=course_run)
        mock_create_enrollments.return_value = ([enrollment], True)

        payload = {
            "email": user.email,
            "course_id": course_run.courseware_id,
            "role": "instructor",
        }
        response = self._post_webhook(api_client, payload)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["message"] == "Enrollment successful"

    def test_get_method_not_allowed(self, api_client, settings):
        """Test that GET requests are rejected"""
        settings.OPENEDX_WEBHOOK_KEY = TEST_WEBHOOK_KEY
        response = api_client.get(reverse(WEBHOOK_URL))
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
