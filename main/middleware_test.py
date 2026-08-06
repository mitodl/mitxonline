import uuid

import pytest
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse

from main.middleware import AnonymousBasketHandoffMiddleware, HostBasedCSRFMiddleware
from users.factories import UserFactory

pytestmark = [pytest.mark.django_db]


@pytest.mark.parametrize(
    ("host", "expected_domain"),
    [
        ("http://mitxonline.mit.edu", "mitxonline.mit.edu"),
        ("http://api.learn.mit.edu", "api.learn.mit.edu"),
        ("http://learn.mit.edu", "learn.mit.edu"),
        ("http://mitxonline.odl.local:8013", "mitxonline.odl.local"),
        ("http://example.com", ""),
        ("", ""),
        ("not-a-url", ""),
        ("http://", ""),
        ("http://mitxonline.mit.edu:8080", ""),
        ("http://sub.sub.sub.learn.mit.edu", "sub.sub.sub.learn.mit.edu"),
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


def test_anonymous_basket_handoff_no_param_is_a_noop(mocker, rf):
    """Test that a request with no handoff param passes straight through"""
    get_response = mocker.MagicMock()
    middleware = AnonymousBasketHandoffMiddleware(get_response)

    request = rf.get("/cart/")
    request.session = {}
    request.user = AnonymousUser()

    assert middleware.process_request(request) is None


def test_anonymous_basket_handoff_adopts_valid_id(mocker, rf):
    """Test that a valid handoff id is adopted into the session and the param is stripped"""
    get_response = mocker.MagicMock()
    middleware = AnonymousBasketHandoffMiddleware(get_response)

    anon_id = str(uuid.uuid4())
    request = rf.get(f"/cart/?anonymous_basket_id={anon_id}&other=1")
    request.session = {}
    request.user = AnonymousUser()

    response = middleware.process_request(request)

    assert response.status_code == 302
    assert response.url == "/cart/?other=1"
    assert request.session["anonymous_basket_id"] == anon_id


def test_anonymous_basket_handoff_ignores_malformed_id(mocker, rf):
    """Test that a malformed id is not stored, but the param is still stripped"""
    get_response = mocker.MagicMock()
    middleware = AnonymousBasketHandoffMiddleware(get_response)

    request = rf.get("/cart/?anonymous_basket_id=not-a-uuid")
    request.session = {}
    request.user = AnonymousUser()

    response = middleware.process_request(request)

    assert response.status_code == 302
    assert response.url == "/cart/"
    assert "anonymous_basket_id" not in request.session


def test_anonymous_basket_handoff_does_not_overwrite_existing_session(mocker, rf):
    """Test that an id already established in this session takes precedence"""
    get_response = mocker.MagicMock()
    middleware = AnonymousBasketHandoffMiddleware(get_response)

    existing_id = str(uuid.uuid4())
    incoming_id = str(uuid.uuid4())
    request = rf.get(f"/cart/?anonymous_basket_id={incoming_id}")
    request.session = {"anonymous_basket_id": existing_id}
    request.user = AnonymousUser()

    response = middleware.process_request(request)

    assert response.status_code == 302
    assert request.session["anonymous_basket_id"] == existing_id


def test_anonymous_basket_handoff_skips_session_write_when_authenticated(mocker, rf):
    """Test that an authenticated request never has its session mutated by this middleware"""
    get_response = mocker.MagicMock()
    middleware = AnonymousBasketHandoffMiddleware(get_response)

    anon_id = str(uuid.uuid4())
    request = rf.get(f"/cart/?anonymous_basket_id={anon_id}")
    request.session = {}
    request.user = UserFactory.create()

    response = middleware.process_request(request)

    assert response.status_code == 302
    assert "anonymous_basket_id" not in request.session


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
