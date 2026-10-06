"""Tests for cms.credential_metadata"""

import pytest
import requests
import responses

from cms.credential_metadata import (
    CREDENTIAL_METADATA_PATH,
    CredentialMetadataUnavailableError,
    fetch_credential_metadata,
    is_configured,
    render_criteria_markdown,
)

# Deliberately not a real MIT Learn host, so that a mistake which reads the
# production default rather than the configured setting fails to match the
# registered responses instead of quietly passing.
API_BASE_URL = "https://learn-api.test"
METADATA_URL = f"{API_BASE_URL}{CREDENTIAL_METADATA_PATH}"

READABLE_ID = "course-v1:MITxT+2.25.1x"

DESCRIPTION = "A one or two sentence description of the course."
CRITERIA = [
    "Described how machine learning models are trained",
    "Distinguished between symbolic and modern machine learning",
]
CRITERIA_MARKDOWN = (
    "- Described how machine learning models are trained\n"
    "- Distinguished between symbolic and modern machine learning"
)


@pytest.fixture
def learn_api(settings):
    """Point the client at a test host rather than the empty default."""
    settings.MIT_LEARN_API_BASE_URL = API_BASE_URL
    return settings


def test_is_configured_follows_the_setting(settings):
    """The feature is off until a host is configured."""
    settings.MIT_LEARN_API_BASE_URL = ""
    assert is_configured() is False

    settings.MIT_LEARN_API_BASE_URL = API_BASE_URL
    assert is_configured() is True


@responses.activate
def test_fetch_makes_no_request_when_unconfigured(settings):
    """
    An unconfigured deployment reaches nobody.

    The setting defaults to empty precisely so that a fork or a developer who
    has not opted in never sends traffic to an instance they did not choose.
    """
    settings.MIT_LEARN_API_BASE_URL = ""

    assert fetch_credential_metadata(READABLE_ID) is None
    assert not responses.calls


@responses.activate
def test_fetch_returns_stored_metadata(learn_api):
    """Stored text comes back, with criteria rendered to markdown."""
    responses.add(
        responses.GET,
        METADATA_URL,
        json={
            "resource_readable_id": READABLE_ID,
            "description": DESCRIPTION,
            "criteria": CRITERIA,
        },
        status=200,
    )

    metadata = fetch_credential_metadata(READABLE_ID)

    assert metadata is not None
    assert metadata.readable_id == READABLE_ID
    assert metadata.description == DESCRIPTION
    assert metadata.criteria == CRITERIA_MARKDOWN
    assert metadata.errors == {}


@responses.activate
def test_fetch_queries_by_readable_id(learn_api):
    """The course is identified by the resource_readable_id query parameter."""
    responses.add(responses.GET, METADATA_URL, json={}, status=200)

    fetch_credential_metadata(READABLE_ID)

    assert responses.calls[0].request.params == {"resource_readable_id": READABLE_ID}


@responses.activate
def test_fetch_tolerates_a_trailing_slash_on_the_base_url(settings):
    """
    A configured host may carry a trailing slash.

    mit-learn quoted the RC host with one, and a double slash in the path is
    not guaranteed to resolve.
    """
    settings.MIT_LEARN_API_BASE_URL = f"{API_BASE_URL}/"
    responses.add(responses.GET, METADATA_URL, json={}, status=200)

    fetch_credential_metadata(READABLE_ID)

    assert responses.calls[0].request.url.startswith(METADATA_URL)


@responses.activate
def test_fetch_treats_404_as_nothing_stored(learn_api):
    """
    A 404 is an ordinary empty result, not a failure.

    It means mit-learn has generated nothing for this course yet -- which is a
    genuine gap rather than an error the author should be asked to retry.
    """
    responses.add(
        responses.GET, METADATA_URL, json={"detail": "Not found."}, status=404
    )

    assert fetch_credential_metadata(READABLE_ID) is None


@responses.activate
def test_fetch_handles_a_missing_description(learn_api):
    """
    A field mit-learn could not generate is omitted, not blanked.

    The rest of the payload is still usable, and the reason is carried in
    `errors` for the caller to surface.
    """
    responses.add(
        responses.GET,
        METADATA_URL,
        json={
            "resource_readable_id": READABLE_ID,
            "criteria": CRITERIA,
            "errors": {"description": "not enough source content"},
        },
        status=200,
    )

    metadata = fetch_credential_metadata(READABLE_ID)

    assert metadata.description is None
    assert metadata.criteria == CRITERIA_MARKDOWN
    assert metadata.errors == {"description": "not enough source content"}


@responses.activate
def test_fetch_handles_a_missing_criteria(learn_api):
    """A partial response the other way round is equally normal."""
    responses.add(
        responses.GET,
        METADATA_URL,
        json={
            "resource_readable_id": READABLE_ID,
            "description": DESCRIPTION,
            "errors": {"criteria": "no structured learning goals found"},
        },
        status=200,
    )

    metadata = fetch_credential_metadata(READABLE_ID)

    assert metadata.description == DESCRIPTION
    assert metadata.criteria is None
    assert metadata.errors == {"criteria": "no structured learning goals found"}


@responses.activate
def test_fetch_raises_on_a_non_json_body(learn_api):
    """
    A 200 carrying HTML is a failure, not an empty result.

    A partially deployed mit-learn can answer with an error page, and parsing
    that as a missing draft would hide a real outage from the author.
    """
    responses.add(
        responses.GET,
        METADATA_URL,
        body="<html><body>502 Bad Gateway</body></html>",
        status=200,
        content_type="text/html",
    )

    with pytest.raises(CredentialMetadataUnavailableError):
        fetch_credential_metadata(READABLE_ID)


@responses.activate
def test_fetch_raises_on_an_unexpected_payload_shape(learn_api):
    """Valid JSON that is not an object is still unusable."""
    responses.add(responses.GET, METADATA_URL, json=["unexpected"], status=200)

    with pytest.raises(CredentialMetadataUnavailableError):
        fetch_credential_metadata(READABLE_ID)


@responses.activate
def test_fetch_raises_on_an_http_error(learn_api):
    """A server error is reported as unavailable rather than as no draft."""
    responses.add(responses.GET, METADATA_URL, json={"detail": "boom"}, status=500)

    with pytest.raises(CredentialMetadataUnavailableError):
        fetch_credential_metadata(READABLE_ID)


@responses.activate
def test_fetch_raises_on_a_timeout(learn_api):
    """A timeout surfaces as a handleable failure, not a raw requests error."""
    responses.add(
        responses.GET, METADATA_URL, body=requests.exceptions.ConnectTimeout()
    )

    with pytest.raises(CredentialMetadataUnavailableError):
        fetch_credential_metadata(READABLE_ID)


@pytest.mark.parametrize(
    ("criteria", "expected"),
    [
        (CRITERIA, CRITERIA_MARKDOWN),
        (["- Already bulleted", "Not bulleted"], "- Already bulleted\n- Not bulleted"),
        (["* Asterisk bullet"], "* Asterisk bullet"),
        (["  Padded  ", "Second"], "- Padded\n- Second"),
        (["", "   ", "Only real one"], "- Only real one"),
        ([], None),
        (None, None),
        (["", "   "], None),
    ],
)
def test_render_criteria_markdown(criteria, expected):
    """
    mit-learn returns criteria as a list; the CMS field stores one markdown blob.

    An existing bullet is left alone rather than doubled up, since the model
    sometimes writes one and sometimes does not.
    """
    assert render_criteria_markdown(criteria) == expected
