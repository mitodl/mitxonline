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

from courses.factories import (
    CourseRunEnrollmentFactory,
    CourseRunFactory,
    CourseRunGradeFactory,
)
from courses.models import (
    CourseRunCertificate,
    CourseRunEnrollment,
)
from openedx.constants import EDX_ENROLLMENT_AUDIT_MODE, EDX_ENROLLMENT_VERIFIED_MODE
from openedx.exceptions import (
    EdxApiNotificationPreferencesError,
    NoEdxApiAuthError,
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
    def non_staff_oauth_token(self, oauth_application):
        """Create a valid OAuth2 access token for a non-staff user"""
        user = UserFactory.create(is_staff=False)
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

    @pytest.mark.parametrize(
        ("auth_scenario", "expected_status"),
        [
            ("none", status.HTTP_401_UNAUTHORIZED),
            ("invalid", status.HTTP_401_UNAUTHORIZED),
            ("expired", status.HTTP_401_UNAUTHORIZED),
            ("non_staff", status.HTTP_403_FORBIDDEN),
        ],
    )
    def test_authentication_and_permission_failures(
        self, request, api_client, webhook_payload, auth_scenario, expected_status
    ):
        """Test that invalid/missing/expired tokens return 401 and non-staff returns 403"""
        token_map = {
            "none": None,
            "invalid": "invalid-token",
            "expired": request.getfixturevalue("expired_oauth_token").token,
            "non_staff": request.getfixturevalue("non_staff_oauth_token").token,
        }
        response = self._post_webhook(
            api_client, webhook_payload, token=token_map[auth_scenario]
        )
        assert response.status_code == expected_status

    @pytest.mark.parametrize("missing_field", ["email", "course_id"])
    def test_missing_required_field(self, api_client, oauth_token, missing_field):
        """Test request missing a required field returns 400"""
        payload = {
            "email": "instructor@example.com",
            "course_id": "course-v1:MITx+1.001x+2025_T1",
            "role": "staff",
        }
        del payload[missing_field]
        response = self._post_webhook(api_client, payload, token=oauth_token.token)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.parametrize(
        ("create_user", "create_course_run"),
        [(False, True), (True, False)],
        ids=["user_not_found", "course_run_not_found"],
    )
    def test_resource_not_found(
        self, api_client, oauth_token, create_user, create_course_run
    ):
        """Test returns 404 when user or course run doesn't exist"""
        email = "nonexistent@example.com"
        course_id = "course-v1:MITx+NONEXISTENT+2025_T1"

        if create_user:
            user = UserFactory.create()
            email = user.email
        if create_course_run:
            course_run = CourseRunFactory.create()
            course_id = course_run.courseware_id

        payload = {"email": email, "course_id": course_id, "role": "instructor"}
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

        assert response.status_code == status.HTTP_200_OK
        assert response.data["message"] == "Enrollment successful"
        assert (
            CourseRunEnrollment.all_objects.filter(user=user, run=course_run).count()
            == 1
        )

    @pytest.mark.parametrize(
        ("payload_mode", "expected_mode"),
        [
            (EDX_ENROLLMENT_VERIFIED_MODE, EDX_ENROLLMENT_VERIFIED_MODE),
            (EDX_ENROLLMENT_AUDIT_MODE, EDX_ENROLLMENT_AUDIT_MODE),
            (None, EDX_ENROLLMENT_AUDIT_MODE),
            ("", EDX_ENROLLMENT_AUDIT_MODE),
        ],
    )
    def test_enrollment_mode(
        self, api_client, oauth_token, payload_mode, expected_mode
    ):
        """The payload mode is honored, falling back to the default mode"""
        user = UserFactory.create()
        course_run = CourseRunFactory.create()

        payload = {
            "email": user.email,
            "course_id": course_run.courseware_id,
        }
        if payload_mode is not None:
            payload["mode"] = payload_mode

        response = self._post_webhook(api_client, payload, token=oauth_token.token)

        assert response.status_code == status.HTTP_201_CREATED
        enrollment = CourseRunEnrollment.all_objects.get(user=user, run=course_run)
        assert enrollment.enrollment_mode == expected_mode

    def test_mode_does_not_change_existing_enrollment(self, api_client, oauth_token):
        """An existing enrollment keeps its mode; the webhook only mirrors state"""
        user = UserFactory.create()
        course_run = CourseRunFactory.create()
        CourseRunEnrollment.all_objects.create(
            user=user,
            run=course_run,
            edx_enrolled=True,
            enrollment_mode=EDX_ENROLLMENT_VERIFIED_MODE,
        )

        payload = {
            "email": user.email,
            "course_id": course_run.courseware_id,
            "mode": EDX_ENROLLMENT_AUDIT_MODE,
        }
        response = self._post_webhook(api_client, payload, token=oauth_token.token)

        assert response.status_code == status.HTTP_200_OK
        enrollment = CourseRunEnrollment.all_objects.get(user=user, run=course_run)
        assert enrollment.enrollment_mode == EDX_ENROLLMENT_VERIFIED_MODE

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


class TestEdxCertificateWebhook:
    """Tests for the edx_certificate_webhook view"""

    WEBHOOK_URL = reverse("openedx-certificate-webhook")

    def test_unauthenticated_returns_401(self):
        """Test that unauthenticated requests are rejected"""
        client = APIClient()
        response = client.post(
            self.WEBHOOK_URL,
            {"email": "test@example.com", "course_id": "course-v1:MITx+1+2024"},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_non_admin_returns_403(self, user_drf_client):
        """Test that non-admin authenticated users are rejected"""
        response = user_drf_client.post(
            self.WEBHOOK_URL,
            {"email": "test@example.com", "course_id": "course-v1:MITx+1+2024"},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.parametrize(
        "payload, expected_error_field",  # noqa: PT006
        [
            ({"course_id": "course-v1:MITx+1+2024"}, "email"),
            ({"email": "test@example.com"}, "course_id"),
            ({}, None),
        ],
    )
    def test_missing_fields_returns_400(
        self, admin_drf_client, payload, expected_error_field
    ):
        """Test that missing required fields return 400"""
        response = admin_drf_client.post(
            self.WEBHOOK_URL,
            payload,
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        if expected_error_field:
            assert expected_error_field in response.data["error"]

    @pytest.mark.parametrize(
        ("user_email", "courseware_id"),
        [
            ("nonexistent@example.com", None),
            (None, "course-v1:NonExistent+0+2099"),
        ],
        ids=["user_not_found", "course_run_not_found"],
    )
    def test_not_found_returns_404(
        self, admin_drf_client, user, user_email, courseware_id
    ):
        """Test that a non-existent user or course run returns 404"""
        if courseware_id is None:
            courseware_id = CourseRunFactory.create().courseware_id
        if user_email is None:
            user_email = user.email

        response = admin_drf_client.post(
            self.WEBHOOK_URL,
            {"email": user_email, "course_id": courseware_id},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.data["error"]

    @pytest.mark.parametrize(
        (
            "enrollment_mode",
            "grade",
            "passed",
            "is_self_paced",
            "cert_should_exist",
        ),
        [
            (EDX_ENROLLMENT_VERIFIED_MODE, 0.80, True, True, True),
            (EDX_ENROLLMENT_VERIFIED_MODE, 0.80, True, False, True),
            (EDX_ENROLLMENT_VERIFIED_MODE, 0.30, False, True, False),
            (EDX_ENROLLMENT_AUDIT_MODE, 0.80, True, True, False),
        ],
        ids=[
            "verified_passed_self_paced",
            "verified_passed_instructor_paced",
            "verified_not_passed",
            "audit_passed",
        ],
    )
    def test_certificate_status(  # noqa: PLR0913
        self,
        mocker,
        admin_drf_client,
        user,
        enrollment_mode,
        grade,
        passed,
        is_self_paced,
        cert_should_exist,
    ):
        """Test certificate creation based on enrollment mode and grade"""
        course_run = CourseRunFactory.create(is_self_paced=is_self_paced)
        CourseRunEnrollmentFactory.create(
            user=user, run=course_run, enrollment_mode=enrollment_mode
        )
        grade_obj = CourseRunGradeFactory.create(
            course_run=course_run, user=user, grade=grade, passed=passed
        )

        mocker.patch("courses.signals.upsert_custom_properties")
        mocker.patch("hubspot_sync.api.upsert_custom_properties")
        mocker.patch(
            "courses.api.get_edx_grades_with_users",
            return_value=iter([(grade_obj, user)]),
        )
        mocker.patch(
            "courses.api.ensure_course_run_grade",
            return_value=(grade_obj, True, False),
        )

        response = admin_drf_client.post(
            self.WEBHOOK_URL,
            {"email": user.email, "course_id": course_run.courseware_id},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert (
            CourseRunCertificate.objects.filter(
                user=user, course_run=course_run
            ).exists()
            == cert_should_exist
        )

    def test_idempotent_certificate_already_exists(
        self,
        mocker,
        admin_drf_client,
        user,
    ):
        """Test that when a certificate already exists the webhook returns 200 without reprocessing"""
        mocker.patch("courses.signals.upsert_custom_properties")
        enrollment = CourseRunEnrollmentFactory.create(
            user=user, enrollment_mode=EDX_ENROLLMENT_VERIFIED_MODE
        )
        course_run = enrollment.run
        passed_grade = CourseRunGradeFactory.create(
            course_run=course_run, user=user, grade=0.80, passed=True
        )

        mocker.patch("hubspot_sync.api.upsert_custom_properties")
        mocker.patch(
            "courses.api.get_edx_grades_with_users",
            return_value=iter([(passed_grade, user)]),
        )
        mocker.patch(
            "courses.api.ensure_course_run_grade",
            return_value=(passed_grade, True, False),
        )

        response1 = admin_drf_client.post(
            self.WEBHOOK_URL,
            {"email": user.email, "course_id": course_run.courseware_id},
            format="json",
        )
        assert response1.status_code == status.HTTP_200_OK
        assert CourseRunCertificate.objects.filter(
            user=user, course_run=course_run
        ).exists()

        mock_generate = mocker.patch("openedx.views.generate_course_run_certificates")

        response2 = admin_drf_client.post(
            self.WEBHOOK_URL,
            {"email": user.email, "course_id": course_run.courseware_id},
            format="json",
        )
        assert response2.status_code == status.HTTP_200_OK
        mock_generate.assert_not_called()
        assert (
            CourseRunCertificate.objects.filter(
                user=user, course_run=course_run
            ).count()
            == 1
        )


NOTIFICATION_PREFERENCES_URL = "notification-preferences"

PREFERENCES_PAYLOAD = {
    "status": "success",
    "show_preferences": True,
    "show_email_preferences": True,
    "data": {
        "discussion": {
            "enabled": True,
            "non_editable": [],
            "notification_types": {
                "new_discussion_post": {
                    "web": False,
                    "push": False,
                    "email": False,
                    "email_cadence": "Daily",
                    "info": "",
                }
            },
        }
    },
}


def test_notification_preferences_requires_auth(client):
    """Anonymous users cannot read notification preferences"""
    response = client.get(reverse(NOTIFICATION_PREFERENCES_URL))
    assert response.status_code in (
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    )


def test_notification_preferences_get(mocker, user_client, user):
    """GET proxies the learner's preferences straight through"""
    api_mock = mocker.patch(
        "openedx.views.get_notification_preferences",
        return_value=PREFERENCES_PAYLOAD,
    )

    response = user_client.get(reverse(NOTIFICATION_PREFERENCES_URL))

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == PREFERENCES_PAYLOAD
    api_mock.assert_called_once_with(user)


def test_notification_preferences_get_not_synced(mocker, user_client):
    """A learner without Open edX auth gets a 409, not a 500"""
    mocker.patch(
        "openedx.views.get_notification_preferences",
        side_effect=NoEdxApiAuthError("not synced"),
    )

    response = user_client.get(reverse(NOTIFICATION_PREFERENCES_URL))

    assert response.status_code == status.HTTP_409_CONFLICT
    assert "detail" in response.json()


def test_notification_preferences_get_upstream_error(mocker, user_client):
    """An upstream failure surfaces as a 502"""
    mocker.patch(
        "openedx.views.get_notification_preferences",
        side_effect=EdxApiNotificationPreferencesError("boom"),
    )

    response = user_client.get(reverse(NOTIFICATION_PREFERENCES_URL))

    assert response.status_code == status.HTTP_502_BAD_GATEWAY


@pytest.mark.parametrize(
    "body",
    [
        {
            "notification_app": "discussion",
            "notification_type": "new_discussion_post",
            "notification_channel": "web",
            "value": True,
        },
        {
            "notification_app": "discussion",
            "notification_type": "grouped_notification",
            "notification_channel": "email_cadence",
            "email_cadence": "Weekly",
        },
    ],
)
def test_notification_preferences_put(mocker, user_client, user, body):
    """PUT forwards a validated single-field change"""
    api_mock = mocker.patch(
        "openedx.views.update_notification_preference",
        return_value={"status": "success"},
    )

    response = user_client.put(
        reverse(NOTIFICATION_PREFERENCES_URL), body, content_type="application/json"
    )

    assert response.status_code == status.HTTP_200_OK
    api_mock.assert_called_once_with(user, body)


@pytest.mark.parametrize(
    "body",
    [
        # boolean channel with no value
        {
            "notification_app": "discussion",
            "notification_type": "new_discussion_post",
            "notification_channel": "email",
        },
        # cadence channel with no cadence
        {
            "notification_app": "discussion",
            "notification_type": "new_discussion_post",
            "notification_channel": "email_cadence",
        },
        # unknown channel
        {
            "notification_app": "discussion",
            "notification_type": "new_discussion_post",
            "notification_channel": "carrier_pigeon",
            "value": True,
        },
        # bad cadence
        {
            "notification_app": "discussion",
            "notification_type": "new_discussion_post",
            "notification_channel": "email_cadence",
            "email_cadence": "Hourly",
        },
        # missing required identifiers
        {"notification_channel": "web", "value": True},
    ],
)
def test_notification_preferences_put_validation(mocker, user_client, body):
    """Malformed changes are rejected locally, never forwarded to the LMS"""
    api_mock = mocker.patch("openedx.views.update_notification_preference")

    response = user_client.put(
        reverse(NOTIFICATION_PREFERENCES_URL), body, content_type="application/json"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    api_mock.assert_not_called()


def test_notification_preferences_put_not_synced(mocker, user_client):
    """A learner without Open edX auth gets a 409 on write too"""
    mocker.patch(
        "openedx.views.update_notification_preference",
        side_effect=NoEdxApiAuthError("not synced"),
    )

    response = user_client.put(
        reverse(NOTIFICATION_PREFERENCES_URL),
        {
            "notification_app": "discussion",
            "notification_type": "new_discussion_post",
            "notification_channel": "web",
            "value": True,
        },
        content_type="application/json",
    )

    assert response.status_code == status.HTTP_409_CONFLICT


def test_notification_preferences_put_throttled_upstream(mocker, user_client):
    """An LMS throttle is passed through as a 429, not flattened to a 502"""
    mocker.patch(
        "openedx.views.update_notification_preference",
        side_effect=EdxApiNotificationPreferencesError("slow down", status_code=429),
    )

    response = user_client.put(
        reverse(NOTIFICATION_PREFERENCES_URL),
        {
            "notification_app": "discussion",
            "notification_type": "new_discussion_post",
            "notification_channel": "web",
            "value": True,
        },
        content_type="application/json",
    )

    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert "wait a moment" in response.json()["detail"]


def test_notification_preferences_get_throttled_upstream(mocker, user_client):
    """A throttled read is also passed through as a 429"""
    mocker.patch(
        "openedx.views.get_notification_preferences",
        side_effect=EdxApiNotificationPreferencesError("slow down", status_code=429),
    )

    response = user_client.get(reverse(NOTIFICATION_PREFERENCES_URL))

    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
