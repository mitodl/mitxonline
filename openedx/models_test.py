"""Tests for openedx models"""

import pytest
from edx_api.course_runs.exceptions import CourseRunAPIError
from requests import HTTPError, Request, Response

from openedx.models import CLONE_ERROR_BODY_MAX_LENGTH, describe_clone_error

STUDIO_ERROR_PAGE = "<!doctype html><title>Studio Server Error | Studio</title>"


def _response(
    status_code, reason, *, url=None, body=STUDIO_ERROR_PAGE, content_type="text/html"
):
    response = Response()
    response.status_code = status_code
    response.reason = reason
    response.headers["Content-Type"] = content_type
    response._content = body.encode()  # noqa: SLF001
    if url:
        response.request = Request("POST", url).prepare()
    return response


def _clone_api_error(response):
    """Build what edx-api-client raises for a failed clone, with its cause."""
    exc = CourseRunAPIError(
        f"Failed to clone course run: {response.status_code} - {response.text}"
    )
    exc.__cause__ = HTTPError(response=response)
    return exc


def test_describe_clone_error_drops_the_response_body():
    """A Studio 500 is summarized by its status and call, not its HTML page."""
    exc = _clone_api_error(
        _response(
            500,
            "Internal Server Error",
            url="https://studio.example.com/api/v1/course_runs/clone/?x=1",
        )
    )

    assert (
        describe_clone_error(exc)
        == "CourseRunAPIError: edX returned HTTP 500 Internal Server Error for POST /api/v1/course_runs/clone/"
    )


@pytest.mark.parametrize(
    ("body", "kept"),
    [
        ('{"destination_course_id": ["Course run already exists."]}', True),
        (f'{{"detail": "{"x" * CLONE_ERROR_BODY_MAX_LENGTH}"}}', False),
    ],
)
def test_describe_clone_error_keeps_a_short_json_body(body, kept):
    """EdX's reason for refusing a request is kept when it is short JSON."""
    exc = _clone_api_error(
        _response(400, "Bad Request", body=body, content_type="application/json")
    )

    expected = "CourseRunAPIError: edX returned HTTP 400 Bad Request"
    assert describe_clone_error(exc) == (f"{expected}: {body}" if kept else expected)


def test_describe_clone_error_http_error_without_request():
    """An HTTPError carrying its own response is summarized the same way."""
    exc = HTTPError(response=_response(502, "Bad Gateway"))

    assert describe_clone_error(exc) == "HTTPError: edX returned HTTP 502 Bad Gateway"


@pytest.mark.parametrize(
    "exc",
    [
        ValueError("Course already exists in edX"),
        HTTPError("500 Server Error"),
        CourseRunAPIError("Failed to get course run: 404"),
    ],
)
def test_describe_clone_error_without_response(exc):
    """An error with no HTTP response keeps its message."""
    assert describe_clone_error(exc) == f"{type(exc).__name__}: {exc}"
