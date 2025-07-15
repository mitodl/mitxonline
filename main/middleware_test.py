import pytest
from django.http import HttpResponse

from main.middleware import HostBasedCSRFMiddleware


@pytest.mark.parametrize(
    ("host", "expected_domain"),
    [
        ("http://mitxonline.mit.edu", "mitxonline.mit.edu"),
        ("http://api.learn.mit.edu", ".learn.mit.edu"),
        ("http://learn.mit.edu", "learn.mit.edu"),
        ("http://mitxonline.odl.local:8013", "mitxonline.odl.local"),
        ("http://example.com", ""),
        ("", ""),
        ("not-a-url", ""),
        ("http://", ""),
        ("http://mitxonline.mit.edu:8080", ""),
        ("http://sub.sub.sub.learn.mit.edu", ".sub.sub.learn.mit.edu"),
        ("http://localhost", ""),
    ],
)
def test_host_based_csrf_middleware(mocker, rf, settings, host, expected_domain):
    """Tests that the CSRF cookie domain is set correctly based on the request host."""
    settings.CSRF_COOKIE_NAME = "csrf_mitxonline"
    settings.CSRF_TRUSTED_ORIGINS = [
        "https://mitxonline.mit.edu",
        "https://learn.mit.edu",
        "https://api.learn.mit.edu",
        "https://sub.sub.sub.learn.mit.edu",
        "http://mitxonline.odl.local:8013",
    ]

    request = rf.get("/some/path")
    request.META["HTTP_REFERER"] = host

    get_response = mocker.MagicMock()
    middleware = HostBasedCSRFMiddleware(get_response)

    response = HttpResponse()
    response.set_cookie(
        settings.CSRF_COOKIE_NAME,
        "dummy_value",
        secure=True,
        httponly=True,
        samesite="Lax",
    )

    processed_response = middleware.process_response(request, response)

    assert (
        processed_response.cookies[settings.CSRF_COOKIE_NAME]["domain"]
        == expected_domain
    )


def test_host_based_csrf_middleware_no_referer(mocker, rf, settings):
    """Test that middleware handles missing referer header gracefully."""
    settings.CSRF_COOKIE_NAME = "csrf_mitxonline"
    settings.CSRF_TRUSTED_ORIGINS = ["https://mitxonline.mit.edu"]

    request = rf.get("/some/path")
    # No HTTP_REFERER set

    get_response = mocker.MagicMock()
    middleware = HostBasedCSRFMiddleware(get_response)

    response = HttpResponse()
    response.set_cookie(settings.CSRF_COOKIE_NAME, "dummy_value")

    processed_response = middleware.process_response(request, response)

    # Domain should not be modified (should remain empty)
    assert processed_response.cookies[settings.CSRF_COOKIE_NAME]["domain"] == ""
