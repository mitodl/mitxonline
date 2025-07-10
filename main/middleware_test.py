import pytest
from django.http import HttpResponse

from main.middleware import HostBasedCSRFMiddleware


@pytest.mark.parametrize(
    ("host", "expected_domain"),
    [
        ("mitxonline.mit.edu", "mitxonline.mit.edu"),
        ("api.learn.mit.edu", ".learn.mit.edu"),
        ("learn.mit.edu", "learn.mit.edu"),
        ("example.com", ""),
    ],
)
def test_host_based_csrf_middleware(mocker, rf, settings, host, expected_domain):
    """Tests that the CSRF cookie domain is set correctly based on the request host."""
    settings.CSRF_COOKIE_NAME = "csrftoken"
    settings.CSRF_TRUSTED_ORIGINS = [
        "https://mitxonline.mit.edu",
        "https://learn.mit.edu",
        "https://api.learn.mit.edu",
    ]

    request = rf.get("/some/path")
    request.META["HTTP_HOST"] = host

    get_response = mocker.MagicMock()
    middleware = HostBasedCSRFMiddleware(get_response)

    response = HttpResponse()
    response.set_cookie(settings.CSRF_COOKIE_NAME, "dummy_value")

    processed_response = middleware.process_response(request, response)

    assert (
        processed_response.cookies[settings.CSRF_COOKIE_NAME]["domain"]
        == expected_domain
    )
