"""Test openedx views"""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.shortcuts import reverse
from mitol.common.utils.datetime import now_in_utc
from oauth2_provider.models import AccessToken, Application
from oauthlib.common import generate_token
from rest_framework import status
from rest_framework.test import APIClient

from courses.factories import CourseRunFactory, ProgramFactory
from courses.models import (
    CourseRunEnrollment,
    ProgramEnrollment,
    ProgramRequirement,
    ProgramRequirementNodeType,
)
from users.factories import UserFactory

pytestmark = [pytest.mark.django_db]

WEBHOOK_URL = "openedx-enrollment-webhook"


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
    def oauth_application(self):
        """Create an OAuth2 application"""
        return Application.objects.create(
            name="edx-oauth-app",
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
        )

    @pytest.fixture
    def oauth_token(self, oauth_application):
        """Create a valid OAuth2 access token"""
        user = UserFactory.create(is_staff=True)
        return AccessToken.objects.create(
            user=user,
            application=oauth_application,
            token=generate_token(),
            expires=now_in_utc() + timedelta(hours=1),
        )

    @pytest.fixture
    def expired_oauth_token(self, oauth_application):
        """Create an expired OAuth2 access token"""
        user = UserFactory.create(is_staff=True)
        return AccessToken.objects.create(
            user=user,
            application=oauth_application,
            token=generate_token(),
            expires=now_in_utc() - timedelta(hours=1),
        )

    @pytest.fixture
    def webhook_payload(self):
        """Standard webhook payload"""
        return {
            "email": "instructor@example.com",
            "course_id": "course-v1:MITx+1.001x+2025_T1",
            "role": "instructor",
        }

    def _post_webhook(self, api_client, payload, token=None):
        """Helper to POST to the webhook with OAuth2 Bearer auth"""
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
    def test_successful_enrollment(self, api_client, oauth_token, role):
        """Test successful enrollment of a user as auditor via webhook"""
        user = UserFactory.create()
        course_run = CourseRunFactory.create()

        payload = {
            "email": user.email,
            "course_id": course_run.courseware_id,
            "role": role,
        }
        response = self._post_webhook(api_client, payload, token=oauth_token.token)

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["message"] == "Enrollment successful"
        assert response.data["edx_enrolled"] is True

        enrollment = CourseRunEnrollment.all_objects.get(user=user, run=course_run)
        assert enrollment.active is True
        assert enrollment.edx_enrolled is True
        assert enrollment.enrollment_mode == "audit"

    def test_missing_authorization_header(self, api_client, webhook_payload):
        """Test request without Authorization header returns 401"""
        response = api_client.post(
            reverse(WEBHOOK_URL),
            data=webhook_payload,
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_invalid_token(self, api_client, webhook_payload):
        """Test request with invalid Bearer token returns 401"""
        response = self._post_webhook(
            api_client,
            webhook_payload,
            token="invalid-token",  # noqa: S106
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_expired_token(self, api_client, webhook_payload, expired_oauth_token):
        """Test request with expired OAuth2 token returns 401"""
        response = self._post_webhook(
            api_client, webhook_payload, token=expired_oauth_token.token
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_missing_email(self, api_client, oauth_token):
        """Test request missing email returns 400"""
        payload = {"course_id": "course-v1:MITx+1.001x+2025_T1", "role": "staff"}
        response = self._post_webhook(api_client, payload, token=oauth_token.token)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_missing_course_id(self, api_client, oauth_token):
        """Test request missing course_id returns 400"""
        payload = {"email": "instructor@example.com", "role": "staff"}
        response = self._post_webhook(api_client, payload, token=oauth_token.token)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_user_not_found(self, api_client, oauth_token):
        """Test returns 404 when the user email doesn't exist"""
        course_run = CourseRunFactory.create()
        payload = {
            "email": "nonexistent@example.com",
            "course_id": course_run.courseware_id,
            "role": "instructor",
        }
        response = self._post_webhook(api_client, payload, token=oauth_token.token)
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.data["error"]

    def test_course_run_not_found(self, api_client, oauth_token):
        """Test returns 404 when the course run doesn't exist"""
        user = UserFactory.create()
        payload = {
            "email": user.email,
            "course_id": "course-v1:MITx+NONEXISTENT+2025_T1",
            "role": "instructor",
        }
        response = self._post_webhook(api_client, payload, token=oauth_token.token)
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.data["error"]

    @patch(
        "openedx.views.create_local_enrollment",
        side_effect=Exception("Unexpected error"),
    )
    def test_enrollment_creation_exception(
        self,
        mock_create_local,  # noqa: ARG002
        api_client,
        oauth_token,
    ):
        """Test returns 500 when enrollment creation raises an exception"""
        user = UserFactory.create()
        course_run = CourseRunFactory.create()

        payload = {
            "email": user.email,
            "course_id": course_run.courseware_id,
            "role": "instructor",
        }
        response = self._post_webhook(api_client, payload, token=oauth_token.token)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Failed to create enrollment" in response.data["error"]

    def test_already_enrolled_user(self, api_client, oauth_token):
        """Test that webhook succeeds for an already-enrolled user (idempotent)"""
        user = UserFactory.create()
        course_run = CourseRunFactory.create()
        CourseRunEnrollment.all_objects.create(
            user=user,
            run=course_run,
            edx_enrolled=True,
            enrollment_mode="audit",
        )

        payload = {
            "email": user.email,
            "course_id": course_run.courseware_id,
            "role": "instructor",
        }
        response = self._post_webhook(api_client, payload, token=oauth_token.token)

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["message"] == "Enrollment successful"
        assert (
            CourseRunEnrollment.all_objects.filter(user=user, run=course_run).count()
            == 1
        )

    def test_auto_enrolls_in_associated_program(self, api_client, oauth_token):
        """Test that webhook auto-enrolls user in programs associated with the course"""
        user = UserFactory.create()
        course_run = CourseRunFactory.create()
        program = ProgramFactory.create(live=True)

        # Build proper tree structure for program requirements
        root_node = program.requirements_root
        operator_node = root_node.add_child(
            node_type=ProgramRequirementNodeType.OPERATOR,
            operator=ProgramRequirement.Operator.ALL_OF,
            title="Required Courses",
        )
        operator_node.add_child(
            node_type=ProgramRequirementNodeType.COURSE,
            course=course_run.course,
        )

        payload = {
            "email": user.email,
            "course_id": course_run.courseware_id,
            "role": "instructor",
        }
        response = self._post_webhook(api_client, payload, token=oauth_token.token)

        assert response.status_code == status.HTTP_201_CREATED
        assert ProgramEnrollment.objects.filter(user=user, program=program).exists()

    def test_no_edx_api_call(self, api_client, oauth_token):
        """Test that the webhook does NOT call back to edX API"""
        user = UserFactory.create()
        course_run = CourseRunFactory.create()

        payload = {
            "email": user.email,
            "course_id": course_run.courseware_id,
            "role": "instructor",
        }

        with patch("openedx.api.enroll_in_edx_course_runs") as mock_edx_enroll:
            response = self._post_webhook(api_client, payload, token=oauth_token.token)
            mock_edx_enroll.assert_not_called()

        assert response.status_code == status.HTTP_201_CREATED

    def test_get_method_not_allowed(self, api_client, oauth_token):
        """Test that GET requests are rejected"""
        response = api_client.get(
            reverse(WEBHOOK_URL),
            HTTP_AUTHORIZATION=f"Bearer {oauth_token.token}",
        )
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
