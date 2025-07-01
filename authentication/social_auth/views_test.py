"""Tests for authentication views"""

# pylint: disable=redefined-outer-name
from contextlib import ExitStack, contextmanager
from unittest.mock import patch

import factory
import pytest
from django.contrib.auth import get_user, get_user_model
from django.core import mail
from django.db import transaction
from django.test import Client, override_settings
from django.urls import reverse
from faker import Faker
from hypothesis import Verbosity
from hypothesis import settings as hypothesis_settings
from hypothesis import strategies as st
from hypothesis.extra.django import TestCase as HTestCase
from hypothesis.stateful import (
    Bundle,
    HealthCheck,
    RuleBasedStateMachine,
    consumes,
    precondition,
    rule,
)
from mitol.common.pytest_utils import any_instance_of
from pytest_lazy_fixtures import lf
from rest_framework import status
from social_core.backends.email import EmailAuth

from authentication.social_auth.serializers import (
    PARTIAL_PIPELINE_TOKEN_KEY,
)
from authentication.utils import SocialAuthState
from main.constants import USER_MSG_COOKIE_NAME, USER_MSG_TYPE_COMPLETED_AUTH
from main.test_utils import MockResponse
from main.utils import encode_json_cookie_value
from users.factories import UserFactory, UserSocialAuthFactory

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.urls("authentication.social_auth.pytest_urls"),
]

NEW_EMAIL = "test@example.com"
NEXT_URL = "/next/url"

User = get_user_model()

fake = Faker()

# pylint: disable=too-many-public-methods


@pytest.fixture
def email_user(user):
    """Fixture for a user that has an 'email' type UserSocialAuth"""
    UserSocialAuthFactory.create(user=user, provider=EmailAuth.name, uid=user.email)
    return user


# pylint: disable=too-many-arguments
def assert_api_call(  # noqa: PLR0913
    client,
    url,
    payload,
    expected,
    expect_authenticated=False,  # noqa: FBT002
    expect_status=status.HTTP_200_OK,
    use_defaults=True,  # noqa: FBT002
):
    """Runs the API call, performs basic assertions, and returns the response"""
    assert bool(get_user(client).is_authenticated) is False

    response = client.post(reverse(url), payload, content_type="application/json")

    defaults = {
        "errors": [],
        "field_errors": {},
        "redirect_url": None,
        "extra_data": {},
        "state": "error",
        "provider": EmailAuth.name,
        "flow": None,
        "partial_token": any_instance_of(str),
    }

    assert response.json() == ({**defaults, **expected} if use_defaults else expected)
    assert response.status_code == expect_status

    assert bool(get_user(client).is_authenticated) is expect_authenticated

    return response


# pylint: disable=too-many-arguments
def assert_api_call_json(  # noqa: PLR0913
    client,
    url,
    payload,
    expected,
    expect_authenticated=False,  # noqa: FBT002
    expect_status=status.HTTP_200_OK,
    use_defaults=True,  # noqa: FBT002
):
    """Runs the API call, performs basic assertions, and returns the response JSON"""
    response = assert_api_call(
        client=client,
        url=url,
        payload=payload,
        expected=expected,
        expect_authenticated=expect_authenticated,
        expect_status=expect_status,
        use_defaults=use_defaults,
    )
    return response.json()


@pytest.fixture
def mock_email_send(mocker):
    """Mock the email send API"""
    return mocker.patch("mail.verification_api.send_verification_email")


@contextmanager
def noop():
    """A no-op context manager"""
    yield


class AuthStateMachine(RuleBasedStateMachine):
    """
    State machine for auth flows

    How to understand this code:

    This code exercises our social auth APIs, which is basically a graph of nodes and edges that the user traverses.
    You can understand the bundles defined below to be the nodes and the methods of this class to be the edges.

    If you add a new state to the auth flows, create a new bundle to represent that state and define
    methods to define transitions into and (optionally) out of that state.
    """

    # pylint: disable=too-many-instance-attributes

    ConfirmationSentAuthStates = Bundle("confirmation-sent")
    ConfirmationRedeemedAuthStates = Bundle("confirmation-redeemed")
    LoginPasswordAuthStates = Bundle("login-password")
    LoginPasswordAbandonedAuthStates = Bundle("login-password-abandoned")

    recaptcha_patcher = patch(
        "authentication.social_auth.views.requests.post",
        return_value=MockResponse(
            content='{"success": true}', status_code=status.HTTP_200_OK
        ),
    )
    email_send_patcher = patch(
        "mail.verification_api.send_verification_email", autospec=True
    )
    mock_api_patcher = patch(
        "users.serializers.UserSerializer.validate_username",
        return_value="dummy-username",
    )
    mock_edx_username_patcher = patch(
        "users.serializers.validate_username_email_with_edx",
        return_value={"username": "", "email": ""},
    )
    openedx_api_patcher = patch("authentication.pipeline.user.openedx_api")
    openedx_tasks_patcher = patch("authentication.pipeline.user.openedx_tasks")

    def __init__(self):
        """Setup the machine"""
        super().__init__()
        # wrap the execution in a django transaction, similar to django's TestCase
        self.atomic = transaction.atomic()
        self.atomic.__enter__()

        # wrap the execution in a patch()
        self.mock_email_send = self.email_send_patcher.start()
        self.mock_api = self.mock_api_patcher.start()
        self.mock_edx_username_api = self.mock_edx_username_patcher.start()
        self.mock_openedx_api = self.openedx_api_patcher.start()
        self.mock_openedx_tasks = self.openedx_tasks_patcher.start()

        # django test client
        self.client = Client()

        # shared data
        self.email = fake.email()
        self.user = None
        self.password = "password123"  # noqa: S105

        # track whether we've hit an action that starts a flow or not
        self.flow_started = False

    def teardown(self):
        """Cleanup from a run"""
        # clear the mailbox
        del mail.outbox[:]

        # stop the patches
        self.email_send_patcher.stop()
        self.openedx_api_patcher.stop()
        self.openedx_tasks_patcher.stop()
        self.mock_api_patcher.stop()
        self.mock_edx_username_patcher.stop()

        # end the transaction with a rollback to cleanup any state
        transaction.set_rollback(True)
        self.atomic.__exit__(None, None, None)

    def create_existing_user(self):
        """Create an existing user"""
        self.user = UserFactory.create(email=self.email)
        self.user.set_password(self.password)
        self.user.save()
        UserSocialAuthFactory.create(
            user=self.user, provider=EmailAuth.name, uid=self.user.email
        )

    @rule(
        target=ConfirmationSentAuthStates,
        recaptcha_enabled=st.sampled_from([True, False]),
    )
    @precondition(lambda self: not self.flow_started)
    def register_email_not_exists(self, recaptcha_enabled):
        """Register email not exists"""
        self.flow_started = True

        with ExitStack() as stack:
            mock_recaptcha_success = None
            if recaptcha_enabled:
                mock_recaptcha_success = stack.enter_context(self.recaptcha_patcher)
                stack.enter_context(override_settings(**{"RECAPTCHA_SITE_KEY": "fake"}))
            response_json = assert_api_call_json(
                self.client,
                "psa-register-email",
                {
                    "flow": SocialAuthState.FLOW_REGISTER,
                    "email": self.email,
                    **({"recaptcha": "fake"} if recaptcha_enabled else {}),
                },
                {
                    "flow": SocialAuthState.FLOW_REGISTER,
                    "partial_token": None,
                    "state": SocialAuthState.STATE_REGISTER_CONFIRM_SENT,
                },
            )
            self.mock_email_send.assert_called_once()
            if mock_recaptcha_success:
                mock_recaptcha_success.assert_called_once()
            return response_json

    @rule(
        target=LoginPasswordAuthStates, recaptcha_enabled=st.sampled_from([True, False])
    )
    @precondition(lambda self: not self.flow_started)
    def register_email_exists(self, recaptcha_enabled):
        """Register email exists"""
        self.flow_started = True
        self.create_existing_user()

        with ExitStack() as stack:
            mock_recaptcha_success = None
            if recaptcha_enabled:
                mock_recaptcha_success = stack.enter_context(self.recaptcha_patcher)
                stack.enter_context(override_settings(**{"RECAPTCHA_SITE_KEY": "fake"}))

            response_json = assert_api_call_json(
                self.client,
                "psa-register-email",
                {
                    "flow": SocialAuthState.FLOW_REGISTER,
                    "email": self.email,
                    "next": NEXT_URL,
                    **({"recaptcha": "fake"} if recaptcha_enabled else {}),
                },
                {
                    "flow": SocialAuthState.FLOW_REGISTER,
                    "state": SocialAuthState.STATE_LOGIN_PASSWORD,
                    "errors": ["Password is required to login"],
                },
            )
            self.mock_email_send.assert_not_called()
            if mock_recaptcha_success:
                mock_recaptcha_success.assert_called_once()
            return response_json

    @rule()
    @precondition(lambda self: not self.flow_started)
    def register_email_not_exists_with_recaptcha_invalid(self):
        """Yield a function for this step"""
        self.flow_started = True
        with (
            patch(
                "authentication.social_auth.views.requests.post",
                return_value=MockResponse(
                    content='{"success": false, "error-codes": ["bad-request"]}',
                    status_code=status.HTTP_200_OK,
                ),
            ) as mock_recaptcha_failure,
            override_settings(**{"RECAPTCHA_SITE_KEY": "fakse"}),
        ):
            assert_api_call_json(
                self.client,
                "psa-register-email",
                {
                    "flow": SocialAuthState.FLOW_REGISTER,
                    "email": NEW_EMAIL,
                    "recaptcha": "fake",
                },
                {"error-codes": ["bad-request"], "success": False},
                expect_status=status.HTTP_400_BAD_REQUEST,
                use_defaults=False,
            )
            mock_recaptcha_failure.assert_called_once()
            self.mock_email_send.assert_not_called()

    @rule()
    @precondition(lambda self: not self.flow_started)
    def login_email_not_exists(self):
        """Login for an email that doesn't exist"""
        self.flow_started = True
        assert_api_call_json(
            self.client,
            "psa-login-email",
            {"flow": SocialAuthState.FLOW_LOGIN, "email": self.email},
            {
                "field_errors": {"email": "Couldn't find your account"},
                "flow": SocialAuthState.FLOW_LOGIN,
                "partial_token": None,
                "state": SocialAuthState.STATE_REGISTER_REQUIRED,
            },
        )
        assert User.objects.filter(email=self.email).exists() is False

    @rule(target=LoginPasswordAuthStates)
    @precondition(lambda self: not self.flow_started)
    def login_email_exists(self):
        """Login with a user that exists"""
        self.flow_started = True
        self.create_existing_user()

        return assert_api_call_json(
            self.client,
            "psa-login-email",
            {
                "flow": SocialAuthState.FLOW_LOGIN,
                "email": self.user.email,
                "next": NEXT_URL,
            },
            {
                "flow": SocialAuthState.FLOW_LOGIN,
                "state": SocialAuthState.STATE_LOGIN_PASSWORD,
                "extra_data": {},
            },
        )

    @rule(auth_state=consumes(LoginPasswordAuthStates))
    def login_password_valid(self, auth_state):
        """Login with a valid password"""
        assert_api_call_json(
            self.client,
            "psa-login-password",
            {
                "flow": auth_state["flow"],
                "partial_token": auth_state["partial_token"],
                "password": self.password,
            },
            {
                "flow": auth_state["flow"],
                "redirect_url": NEXT_URL,
                "partial_token": None,
                "state": SocialAuthState.STATE_SUCCESS,
            },
            expect_authenticated=True,
        )

    @rule(target=LoginPasswordAuthStates, auth_state=consumes(LoginPasswordAuthStates))
    def login_password_invalid(self, auth_state):
        """Login with an invalid password"""
        return assert_api_call_json(
            self.client,
            "psa-login-password",
            {
                "flow": auth_state["flow"],
                "partial_token": auth_state["partial_token"],
                "password": "invalidpass",
            },
            {
                "field_errors": {
                    "password": "Unable to login with that email and password combination"
                },
                "flow": auth_state["flow"],
                "state": SocialAuthState.STATE_ERROR,
            },
        )

    @rule(
        auth_state=consumes(LoginPasswordAuthStates),
        verify_exports=st.sampled_from([True, False]),
    )
    def login_password_user_inactive(self, auth_state, verify_exports):  # noqa: ARG002
        """Login for an inactive user"""
        self.user.is_active = False
        self.user.save()

        assert_api_call_json(
            self.client,
            "psa-login-password",
            {
                "flow": auth_state["flow"],
                "partial_token": auth_state["partial_token"],
                "password": self.password,
            },
            {
                "flow": auth_state["flow"],
                "redirect_url": None,
                "state": SocialAuthState.STATE_ERROR,
                "field_errors": {
                    "password": "Unable to login with that email and password combination"
                },
            },
            expect_authenticated=False,
        )

    @rule(
        target=ConfirmationRedeemedAuthStates,
        auth_state=consumes(ConfirmationSentAuthStates),
    )
    def redeem_confirmation_code(self, auth_state):
        """Redeem a registration confirmation code"""
        _, _, code, partial_token = self.mock_email_send.call_args[0]
        return assert_api_call_json(
            self.client,
            "psa-register-confirm",
            payload={
                "flow": auth_state["flow"],
                "verification_code": code.code,
                "partial_token": partial_token,
            },
            expected={
                "flow": auth_state["flow"],
                "state": SocialAuthState.STATE_REGISTER_DETAILS,
            },
        )

    @rule(auth_state=consumes(ConfirmationRedeemedAuthStates))
    def redeem_confirmation_code_twice(self, auth_state):
        """Redeeming a code twice should fail"""
        _, _, code, partial_token = self.mock_email_send.call_args[0]
        assert_api_call_json(
            self.client,
            "psa-register-confirm",
            payload={
                "flow": auth_state["flow"],
                "verification_code": code.code,
                "partial_token": partial_token,
            },
            expected={
                "errors": [],
                "flow": auth_state["flow"],
                "redirect_url": None,
                "partial_token": None,
                "state": SocialAuthState.STATE_INVALID_LINK,
            },
        )

    @rule(auth_state=consumes(ConfirmationRedeemedAuthStates))
    def redeem_confirmation_code_twice_existing_user(self, auth_state):
        """Redeeming a code twice with an existing user should fail with existing account state"""
        _, _, code, partial_token = self.mock_email_send.call_args[0]
        self.create_existing_user()
        assert_api_call_json(
            self.client,
            "psa-register-confirm",
            {
                "flow": auth_state["flow"],
                "verification_code": code.code,
                "partial_token": partial_token,
            },
            {
                "errors": [],
                "flow": auth_state["flow"],
                "redirect_url": None,
                "partial_token": None,
                "state": SocialAuthState.STATE_EXISTING_ACCOUNT,
            },
        )

    @rule(
        auth_state=consumes(ConfirmationRedeemedAuthStates),
    )
    def register_details(self, auth_state):
        """Complete the register confirmation details page"""
        payload = {
            "flow": auth_state["flow"],
            "partial_token": auth_state["partial_token"],
            "password": self.password,
            "name": "Sally Smith",
            "username": "custom-username",
            "legal_address": {
                "first_name": "Sally",
                "last_name": "Smith",
                "country": "US",
                "state": "US-MA",
            },
        }

        response = assert_api_call(
            self.client,
            "psa-register-details",
            payload=payload,
            expected={
                "flow": auth_state["flow"],
                "state": SocialAuthState.STATE_SUCCESS,
                "partial_token": None,
            },
            expect_authenticated=True,
        )
        # User message should be included in the cookies
        assert USER_MSG_COOKIE_NAME in response.cookies
        assert response.cookies[USER_MSG_COOKIE_NAME].value == encode_json_cookie_value(
            {
                "type": USER_MSG_TYPE_COMPLETED_AUTH,
            }
        )
        self.user = User.objects.get(email=self.email)
        return response.json()


AuthStateMachine.TestCase.settings = hypothesis_settings(
    max_examples=100,
    stateful_step_count=10,
    deadline=None,
    verbosity=Verbosity.normal,
    suppress_health_check=[HealthCheck.filter_too_much],
)


class AuthStateTestCase(HTestCase, AuthStateMachine.TestCase):
    """TestCase for AuthStateMachine"""


@pytest.mark.usefixtures("mock_email_send")
def test_new_register_no_session_partial(client):
    """
    When a user registers for the first time and a verification email is sent, the partial
    token should be cleared from the session. The Partial object associated with that token should
    only be used when it's matched from the email verification link.
    """
    assert_api_call_json(
        client,
        "psa-register-email",
        {"flow": SocialAuthState.FLOW_REGISTER, "email": NEW_EMAIL},
        {
            "flow": SocialAuthState.FLOW_REGISTER,
            "partial_token": None,
            "state": SocialAuthState.STATE_REGISTER_CONFIRM_SENT,
        },
    )
    assert PARTIAL_PIPELINE_TOKEN_KEY not in client.session.keys()  # noqa: SIM118


def test_login_email_error(client, mocker):
    """Tests email login with error result"""
    assert bool(get_user(client).is_authenticated) is False

    mocked_authenticate = mocker.patch(
        "authentication.social_auth.serializers.SocialAuthSerializer._authenticate"
    )
    mocked_authenticate.return_value = "invalid"

    # start login with email
    response = client.post(
        reverse("psa-login-email"),
        {"flow": SocialAuthState.FLOW_LOGIN, "email": "anything@example.com"},
    )
    assert response.json() == {
        "errors": [],
        "field_errors": {"email": "Couldn't find your account"},
        "flow": SocialAuthState.FLOW_LOGIN,
        "provider": EmailAuth.name,
        "redirect_url": None,
        "partial_token": None,
        "state": SocialAuthState.STATE_REGISTER_REQUIRED,
        "extra_data": {},
    }
    assert response.status_code == status.HTTP_200_OK

    assert bool(get_user(client).is_authenticated) is False


def test_login_email_hijacked(client, user, admin_user):
    """Test that a 403 response is returned for email login view if user is hijacked"""
    client.force_login(admin_user)
    client.post("/hijack/acquire/", {"user_pk": user.id})
    response = client.post(
        reverse("psa-login-email"),
        {"flow": SocialAuthState.FLOW_LOGIN, "email": "anything@example.com"},
    )
    assert response.status_code == 403


def test_register_email_hijacked(client, user, admin_user):
    """Test that a 403 response is returned for email register view if user is hijacked"""
    client.force_login(admin_user)
    client.post("/hijack/acquire/", {"user_pk": user.id})
    response = client.post(
        reverse("psa-register-email"),
        {"flow": SocialAuthState.FLOW_LOGIN, "email": "anything@example.com"},
    )
    assert response.status_code == 403


def test_get_social_auth_types(client, user):
    """Verify that get_social_auth_types returns a list of providers that the user has authenticated with"""
    social_auth_providers = ["provider1", "provider2"]
    url = reverse("get-auth-types-api")
    UserSocialAuthFactory.create_batch(
        2, user=user, provider=factory.Iterator(social_auth_providers)
    )
    client.force_login(user)
    resp = client.get(url)
    assert resp.json() == [{"provider": provider} for provider in social_auth_providers]


@pytest.mark.parametrize(
    ("auth_user", "url"),
    [
        (lf("user"), "/logout?no_redirect=1"),
        (None, "/logout?no_redirect=1"),
        (lf("user"), "/logout"),
        (None, "/logout"),
    ],
)
def test_logout(client, auth_user, url):
    """Test that the legacy logout url works"""

    if auth_user is not None:
        client.force_login(auth_user)

    resp = client.get(url)

    assert resp.status_code == status.HTTP_302_FOUND
    assert resp.headers["Location"] == "https://openedx.odl.local/logout"
