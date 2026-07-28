"""Tests for cms.tasks"""

import logging

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

    MIT_LEARN_FASTLY_SERVICE_ID is set to a value the tests never register a
    response for, so that a test meaning to exercise an explicitly passed
    service ID cannot pass by falling back to settings.
    """
    settings.FASTLY_URL = FASTLY_URL
    settings.FASTLY_AUTH_TOKEN = FASTLY_AUTH_TOKEN
    settings.SITE_BASE_URL = SITE_BASE_URL
    settings.MIT_LEARN_FASTLY_SERVICE_ID = "unregistered-fallback-service-id"
    return settings


@responses.activate
def test_queue_fastly_surrogate_key_purge_targets_given_service(fastly_settings):
    """An explicitly passed service ID takes precedence over the setting."""
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
def test_queue_fastly_surrogate_key_purge_sends_hard_purge(fastly_settings):
    """
    The surrogate key purge must be a hard purge -- no Fastly-Soft-Purge header.

    A soft purge only marks objects stale, and MIT Learn serves pages with a long
    stale-while-revalidate window, so each cache node would serve the outdated
    page at least once more instead of refetching from origin.
    """
    responses.add(
        responses.POST,
        f"{FASTLY_URL}/service/{LEARN_SERVICE_ID}/purge/{SURROGATE_KEY}",
        json={"status": "ok"},
        status=200,
    )

    assert queue_fastly_surrogate_key_purge(SURROGATE_KEY, LEARN_SERVICE_ID) is True

    sent_headers = responses.calls[0].request.headers
    assert "fastly-soft-purge" not in {key.lower() for key in sent_headers}


@responses.activate
def test_queue_fastly_surrogate_key_purge_falls_back_to_settings(fastly_settings):
    """
    Called with the surrogate key alone, the task purges Learn's service anyway.

    This is the shape of a message enqueued by a release that does not pass
    service_id, so the fallback is what keeps purges working across a rolling
    deploy rather than silently skipping them.
    """
    fastly_settings.MIT_LEARN_FASTLY_SERVICE_ID = LEARN_SERVICE_ID
    purge = responses.add(
        responses.POST,
        f"{FASTLY_URL}/service/{LEARN_SERVICE_ID}/purge/{SURROGATE_KEY}",
        json={"status": "ok"},
        status=200,
    )

    assert queue_fastly_surrogate_key_purge(SURROGATE_KEY) is True

    assert purge.call_count == 1


@responses.activate
def test_queue_fastly_surrogate_key_purge_skips_without_service_id(
    fastly_settings, caplog
):
    """
    With no service ID passed and none configured, the purge is skipped.

    It must skip rather than raise or request `/service/None/purge/...`, and it
    must say so at error level -- an unconfigured service ID disables cache
    invalidation, and only ERROR and above reaches Sentry as an issue.
    """
    fastly_settings.MIT_LEARN_FASTLY_SERVICE_ID = None

    assert queue_fastly_surrogate_key_purge(SURROGATE_KEY) is False
    assert not responses.calls
    assert [record.levelno for record in caplog.records] == [logging.ERROR]


@responses.activate
def test_queue_fastly_surrogate_key_purge_skips_without_auth_token(
    fastly_settings, caplog
):
    """A missing auth token skips the purge rather than sending it unauthenticated."""
    fastly_settings.FASTLY_AUTH_TOKEN = None

    assert queue_fastly_surrogate_key_purge(SURROGATE_KEY, LEARN_SERVICE_ID) is False
    assert not responses.calls
    assert [record.levelno for record in caplog.records] == [logging.ERROR]


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
