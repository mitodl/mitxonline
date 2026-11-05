"""Tests for the CyberSource REST SDK urllib3 compatibility shim."""

import pytest
from CyberSource import rest

from compliance.api import get_latest_export_compliance_log, verify_user_with_exports
from courses.factories import CourseRunFactory
from main.cybersource_compat import CompatUrllib3, apply_cybersource_urllib3_compat
from users.factories import UserFactory

pytestmark = pytest.mark.django_db

EXPORT_URL = "https://apitest.cybersource.com/risk/v1/export-compliance-inquiries"


@pytest.fixture(autouse=True)
def _isolate_sdk_globals():
    """
    Undo the global state CyberSource.rest keeps between tests.

    `_urllib3_poolmanagers` is a class-level cache that outlives every client instance, and
    `rest.urllib3` is the module global the shim rebinds - a test that re-applies the patch
    must not decide what later tests see.
    """
    original_urllib3 = rest.urllib3
    rest.RESTClientObject._urllib3_poolmanagers.clear()  # noqa: SLF001
    yield
    rest.urllib3 = original_urllib3
    rest.RESTClientObject._urllib3_poolmanagers.clear()  # noqa: SLF001


def test_shim_is_installed_at_startup():
    """RootConfig.ready() should have swapped CyberSource.rest's urllib3 for the shim."""
    assert isinstance(rest.urllib3, CompatUrllib3)


def test_pool_manager_tolerates_urllib3_future_kwargs():
    """
    The SDK's keepalive kwargs must not reach the real urllib3's PoolKey.

    Building the connection pool is what raised
    `TypeError: PoolKey.__new__() got an unexpected keyword argument 'key_keepalive_delay'`.
    """
    manager = rest.urllib3.PoolManager(
        num_pools=4, maxsize=4, keepalive_delay=300, keepalive_idle_window=30
    )

    assert manager.connection_from_url(EXPORT_URL) is not None


def test_proxy_manager_tolerates_urllib3_future_kwargs():
    """The proxy branch of get_pool_manager passes the same kwargs."""
    manager = rest.urllib3.ProxyManager(
        num_pools=4,
        maxsize=4,
        proxy_url="http://proxy.example.com:8080",
        proxy_headers=None,
        keepalive_delay=300,
        keepalive_idle_window=30,
    )

    assert manager.connection_from_url(EXPORT_URL) is not None


def test_shim_delegates_unknown_attributes_to_real_urllib3():
    """CyberSource.rest also uses urllib3 helpers the shim does not wrap."""
    assert rest.urllib3.make_headers(proxy_basic_auth="user:pass") == {
        "proxy-authorization": "Basic dXNlcjpwYXNz"
    }


def test_apply_is_idempotent():
    """ready() can run more than once in a process; re-patching must not stack proxies."""
    patched = rest.urllib3

    apply_cybersource_urllib3_compat()

    assert rest.urllib3 is patched


def test_export_compliance_check_reaches_the_wire(
    urllib3_mock, export_compliance_keypair
):
    """
    Drive the real SDK end to end with only urlopen mocked.

    urllib3_mock patches HTTPConnectionPool.urlopen, which sits below
    PoolManager.connection_from_host - so the pool key construction that used to fail is
    still exercised. Every other compliance test mocks get_cybersource_client, which is
    why none of them caught the urllib3-future kwargs.
    """
    user = UserFactory.create(email="ada@example.com")
    user.legal_address.first_name = "Ada"
    user.legal_address.last_name = "Lovelace"
    user.legal_address.country = "US"
    user.legal_address.street_address_1 = "77 Massachusetts Ave"
    user.legal_address.city = "Cambridge"
    user.legal_address.state = "US-MA"
    user.legal_address.postal_code = "02139"
    user.legal_address.save()
    run = CourseRunFactory.create()

    urllib3_mock.add_response(
        status_code=201,
        url=EXPORT_URL,
        method="POST",
        json={
            "id": "abc123",
            "status": "COMPLETED",
            "exportComplianceInformation": {"infoCodes": ["MATCH-BCO"]},
        },
    )

    result = verify_user_with_exports(user, run)

    assert result.accepted is True
    assert result.decision == "COMPLETED"
    assert result.reason_code == "MATCH-BCO"
    assert result.request_id == "abc123"
    assert get_latest_export_compliance_log(user, run) is not None
