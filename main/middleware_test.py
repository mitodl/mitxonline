import uuid
from urllib.parse import parse_qs, urlparse

import pytest
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse

from ecommerce.factories import BasketFactory
from main.middleware import (
    AnonymousBasketHandoffMiddleware,
    BasketOwnerHandoffMiddleware,
    HostBasedCSRFMiddleware,
)
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


@pytest.fixture
def basket_owner_middleware(mocker):
    """BasketOwnerHandoffMiddleware with a stubbed downstream."""
    return BasketOwnerHandoffMiddleware(mocker.MagicMock())


def test_basket_owner_handoff_passes_when_session_owns_the_basket(
    rf, basket_owner_middleware
):
    """The common case: Learn's hand-off matches, so nothing happens."""
    basket = BasketFactory.create()

    request = rf.get("/cart/", {"basket_id": basket.id})
    request.user = basket.user

    assert basket_owner_middleware.process_request(request) is None


def test_basket_owner_handoff_bounces_when_session_is_a_different_user(
    rf, basket_owner_middleware
):
    """The hq#12763 case: the browser arrived as someone else.

    Learn filled User B's basket over its own domain, then handed the browser
    here where the gateway session still names User A.  The request must be sent
    through switch-session rather than rendering A's cart.
    """
    basket = BasketFactory.create()
    other_user = UserFactory.create()

    request = rf.get("/cart/", {"basket_id": basket.id, "ecom-service": "true"})
    request.user = other_user

    response = basket_owner_middleware.process_request(request)

    assert response is not None
    assert response.url.startswith("/switch-session")
    query = parse_qs(urlparse(response.url).query)
    assert query["next"] == ["/cart/"]
    assert query["session_reset"] == ["1"]
    # Unrelated parameters survive the bounce.
    assert query["ecom-service"] == ["true"]
    assert query["basket_id"] == [str(basket.id)]


def test_basket_owner_handoff_does_not_loop(rf, basket_owner_middleware):
    """A second mismatch proceeds rather than bouncing forever.

    The caller then sees their own session's cart -- the wrong cart for whoever
    clicked, but never a different person's data.
    """
    basket = BasketFactory.create()
    other_user = UserFactory.create()

    request = rf.get(
        "/cart/",
        {"basket_id": basket.id, "session_reset": "1"},
    )
    request.user = other_user

    assert basket_owner_middleware.process_request(request) is None


def test_basket_owner_handoff_skips_the_reset_endpoint(rf, basket_owner_middleware):
    """switch-session is where the fix happens; checking there adds a hop."""
    basket = BasketFactory.create()
    other_user = UserFactory.create()

    request = rf.get("/switch-session/", {"basket_id": basket.id})
    request.user = other_user

    assert basket_owner_middleware.process_request(request) is None


@pytest.mark.parametrize("basket_id", ["", "abc", "1; DROP TABLE", "-1"])
def test_basket_owner_handoff_ignores_unusable_basket_ids(
    rf, basket_owner_middleware, basket_id
):
    """A malformed id is ignored rather than treated as a mismatch."""
    request = rf.get("/cart/", {"basket_id": basket_id})
    request.user = UserFactory.create()

    assert basket_owner_middleware.process_request(request) is None


def test_basket_owner_handoff_ignores_anonymous_callers(rf, basket_owner_middleware):
    """With no user there is nothing to compare; the route's gate decides."""
    basket = BasketFactory.create()

    request = rf.get("/cart/", {"basket_id": basket.id})
    request.user = AnonymousUser()

    assert basket_owner_middleware.process_request(request) is None
