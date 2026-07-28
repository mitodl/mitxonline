"""Tests for cms.tasks"""

import pytest
import responses

from cms.tasks import call_fastly_purge_api, queue_fastly_surrogate_key_purge

# Deliberately not the production default (https://api.fastly.com), so that
# reading these settings at module import time rather than call time would fail
# to match the registered responses.
FASTLY_URL = "https://fastly.test"
SITE_BASE_URL = "https://mitxonline.test"
FASTLY_AUTH_TOKEN = "fastly-token"  # noqa: S105

LEARN_SERVICE_ID = "test-learn-service-id"
SURROGATE_KEY = "mitxonline:course:course-v1:MITx+6.00.1x"


@pytest.fixture
def fastly_settings(settings):
    """
    Configure the Fastly settings the purge tasks read.

    MIT_LEARN_FASTLY_SERVICE_ID is set to a decoy so that a task reading the
    service from settings instead of its argument fails rather than passing on a
    coincidence.
    """
    settings.FASTLY_URL = FASTLY_URL
    settings.FASTLY_AUTH_TOKEN = FASTLY_AUTH_TOKEN
    settings.SITE_BASE_URL = SITE_BASE_URL
    settings.MIT_LEARN_FASTLY_SERVICE_ID = "decoy-service-id-not-used"
    return settings


@responses.activate
def test_queue_fastly_surrogate_key_purge_targets_given_service(fastly_settings):
    """The purge goes to the service ID passed in, not one read from settings."""
    purge = responses.add(
        responses.POST,
        f"{FASTLY_URL}/service/{LEARN_SERVICE_ID}/purge/{SURROGATE_KEY}",
        json={"status": "ok"},
        status=200,
    )

    assert queue_fastly_surrogate_key_purge(SURROGATE_KEY, LEARN_SERVICE_ID) is True

    assert purge.call_count == 1
    assert responses.calls[0].request.headers["Fastly-Key"] == FASTLY_AUTH_TOKEN


@responses.activate
def test_queue_fastly_surrogate_key_purge_skips_without_service_id(fastly_settings):
    """
    A missing service ID skips the purge instead of calling Fastly.

    Called with the surrogate key alone, as a message enqueued by a release
    predating the service_id argument would be during a rolling deploy. The task
    must skip rather than raise or request `/service/None/purge/...`.
    """
    assert queue_fastly_surrogate_key_purge(SURROGATE_KEY) is False
    assert not responses.calls


@responses.activate
def test_queue_fastly_surrogate_key_purge_skips_without_auth_token(fastly_settings):
    """A missing auth token skips the purge rather than sending it unauthenticated."""
    fastly_settings.FASTLY_AUTH_TOKEN = None

    assert queue_fastly_surrogate_key_purge(SURROGATE_KEY, LEARN_SERVICE_ID) is False
    assert not responses.calls


@responses.activate
def test_queue_fastly_surrogate_key_purge_returns_false_on_error(fastly_settings):
    """A Fastly error response is reported as a failure rather than swallowed."""
    responses.add(
        responses.POST,
        f"{FASTLY_URL}/service/{LEARN_SERVICE_ID}/purge/{SURROGATE_KEY}",
        status=503,
    )

    assert queue_fastly_surrogate_key_purge(SURROGATE_KEY, LEARN_SERVICE_ID) is False


@responses.activate
def test_call_fastly_purge_api_targets_mitxonline_by_host(fastly_settings):
    """
    The URL purge identifies MITxOnline's own site by `host`, not by service ID.

    Covers the three settings this helper reads, none of which are exercised
    elsewhere.
    """
    purge = responses.add(
        responses.Response(method="PURGE", url=f"{FASTLY_URL}/catalog/", json={})
    )

    call_fastly_purge_api("/catalog/")

    assert purge.call_count == 1
    sent_headers = responses.calls[0].request.headers
    assert sent_headers["host"] == "mitxonline.test"
    assert sent_headers["fastly-key"] == FASTLY_AUTH_TOKEN
