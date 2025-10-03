"""Common fixtures"""

# pylint: disable=unused-argument, redefined-outer-name
import os

import pytest
import responses
from django.test.client import Client
from rest_framework.test import APIClient
from zeal import zeal_ignore

from users.factories import UserFactory


@pytest.fixture
def user(db):  # noqa: ARG001
    """Creates a user"""
    return UserFactory.create()


@pytest.fixture
def staff_user(db):  # noqa: ARG001
    """Staff user fixture"""
    return UserFactory.create(is_staff=True)


@pytest.fixture
def admin_user(db):  # noqa: ARG001
    """Admin user fixture"""
    return UserFactory.create(is_superuser=True, is_staff=True)


@pytest.fixture
def user_client(user):
    """Django test client that is authenticated with the user"""
    client = Client()
    client.force_login(user)
    return client


@pytest.fixture(scope="session")
def api_client():
    """Django test client that is authenticated with the user"""
    client = Client()
    return client  # noqa: RET504


@pytest.fixture
def staff_client(staff_user):
    """Django test client that is authenticated with the staff user"""
    client = Client()
    client.force_login(staff_user)
    return client


@pytest.fixture
def user_drf_client(user):
    """DRF API test client that is authenticated with the user"""
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def admin_drf_client(admin_user):
    """DRF API test client with admin user"""
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client


@pytest.fixture
def mocked_responses():
    """Mocked responses for requests library"""
    with responses.RequestsMock() as rsps:
        yield rsps


@pytest.fixture
def mock_context(mocker, user):
    """Mocked context for serializers"""
    return {"request": mocker.Mock(user=user)}


@pytest.fixture
def valid_address_dict():
    """Yields a dict that will deserialize into a valid legal address"""
    return dict(  # noqa: C408
        first_name="Test",
        last_name="User",
        country="US",
        state="US-MA",
    )


@pytest.fixture
def invalid_address_dict():
    """Yields a dict that will deserialize into an invalid US legal address"""
    return dict(  # noqa: C408
        first_name="Test",
        last_name="User",
        country="US",
        state="XX",
    )


@pytest.fixture
def address_no_state_dict():
    """Yields a dict that will deserialize into a US legal address with no state"""
    return dict(  # noqa: C408
        first_name="Test",
        last_name="User",
        country="US",
        state=None,
    )


@pytest.fixture
def intl_address_dict():
    """Yields a dict that will deserialize into an valid non-US/CA legal address"""

    return dict(  # noqa: C408
        first_name="Test",
        last_name="User",
        country="JP",
    )


@pytest.fixture
def user_profile_dict():
    """Yields a dict that generates a basic user profile"""

    return dict(  # noqa: C408
        gender=None,
        year_of_birth=1980,
    )


@pytest.fixture(autouse=True)
def webpack_stats(settings):
    """Mocks out webpack stats"""

    directory = "scripts/test/data/webpack-stats/"

    for loader_config in settings.WEBPACK_LOADER.values():
        filename = os.path.basename(loader_config["STATS_FILE"])  # noqa: PTH119, F841

        loader_config["STATS_FILE"] = os.path.join(  # noqa: PTH118
            settings.BASE_DIR, directory, "default.json"
        )


@pytest.fixture(autouse=True)
def check_nplusone(request, settings):
    """Raise nplusone errors"""
    settings.ZEAL_RAISE = True
    if request.node.get_closest_marker("skip_nplusone_check"):
        with zeal_ignore():
            yield
    else:
        yield
