"""Common mitx_online middleware"""

import logging
import uuid
from urllib.parse import urlparse

from django.conf import settings
from django.http import HttpResponseRedirect
from django.middleware.csrf import CsrfViewMiddleware, get_token
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin

log = logging.getLogger(__name__)

ANONYMOUS_BASKET_HANDOFF_PARAM = "anonymous_basket_id"

# The id of the basket MIT Learn filled just before handing the browser over,
# and the marker showing this hand-off has already had one session reset.
EXPECTED_BASKET_PARAM = "basket_id"
SESSION_RESET_PARAM = "session_reset"
# len(str(2**63 - 1)): the longest id a bigint primary key can hold.
MAX_BASKET_ID_DIGITS = 19


class CachelessAPIMiddleware(MiddlewareMixin):
    """Add Cache-Control header to API responses"""

    def process_response(self, request, response):
        """Add a Cache-Control header to an API response"""
        if (
            request.path.startswith("/api/")
            or request.path.startswith("/courses/")
            or request.path.startswith("/checkout/")
        ):
            response["Cache-Control"] = "private, no-store"

        return response


class AnonymousBasketHandoffMiddleware(MiddlewareMixin):
    """
    Adopt an anonymous_basket_id passed as a query parameter into this
    request's own session, then redirect to the same URL with the parameter
    stripped.

    An anonymous basket's session cookie is host-only, and MIT's shared
    mit.edu domain can't be used to widen it (institution-wide cookie size
    limits). Learn's frontend proxies basket API calls through a different
    subdomain than the one that serves mitxonline's own pages, so the
    cookie set during those API calls never reaches this domain on its own -
    the id has to be handed off explicitly through the URL instead.
    """

    def process_request(self, request):
        basket_id = request.GET.get(ANONYMOUS_BASKET_HANDOFF_PARAM)
        if not basket_id:
            return None

        if not request.user.is_authenticated and not request.session.get(
            "anonymous_basket_id"
        ):
            try:
                uuid.UUID(basket_id)
            except ValueError:
                log.warning(
                    "Ignoring malformed anonymous_basket_id query param: %s",
                    basket_id,
                )
            else:
                request.session["anonymous_basket_id"] = basket_id

        query_params = request.GET.copy()
        del query_params[ANONYMOUS_BASKET_HANDOFF_PARAM]
        redirect_url = request.path
        if query_params:
            redirect_url = f"{redirect_url}?{query_params.urlencode()}"

        return HttpResponseRedirect(redirect_url)


class HostBasedCSRFMiddleware(CsrfViewMiddleware):
    """
    CSRF middleware that scopes the response cookie's domain to the origin of
    the page that made the request, when that origin is one of
    settings.CSRF_TRUSTED_ORIGINS.

    A frontend on another host (learn.mit.edu calling api.learn.mit.edu) can
    only read the cookie from document.cookie if its Domain covers the
    frontend, and the request's Host header names the API, not the frontend.
    """

    def process_response(self, request, response):
        # Django issues the CSRF cookie only when a request flags it, and on
        # API paths only auth.login() does, once per session. A logged-in
        # browser that never stored that cookie (its Domain was not settable
        # from this host) would otherwise stay without one for the whole
        # session. Flag it again so this response re-issues it. Only a
        # session-cookie login can be in that state; token clients (OAuth2
        # bearer) never hold a CSRF cookie and would be re-issued one on every
        # response.
        user = getattr(request, "user", None)
        if (
            user is not None
            and user.is_authenticated
            and settings.SESSION_COOKIE_NAME in request.COOKIES
            and settings.CSRF_COOKIE_NAME not in request.COOKIES
        ):
            get_token(request)
        response = super().process_response(request, response)
        # Browsers send Origin on every cross-origin request regardless of the
        # page's referrer policy, so it is present exactly when the cookie has
        # to be scoped to a host other than this one. A request without it is
        # same-origin or not from a browser, and the cookie keeps
        # CSRF_COOKIE_DOMAIN. Referer is deliberately not consulted: it is
        # subject to the referrer policy and can be absent on the very requests
        # that need the rewrite.
        origin = request.headers.get("origin")
        if settings.CSRF_COOKIE_NAME in response.cookies and origin:
            host = urlparse(origin).netloc
            csrf_trusted_hosts = []
            for trusted_origin in getattr(settings, "CSRF_TRUSTED_ORIGINS", []):
                parsed_origin = urlparse(trusted_origin)
                if parsed_origin.netloc:
                    csrf_trusted_hosts.append(parsed_origin.netloc)
            if host in csrf_trusted_hosts:
                response.cookies[settings.CSRF_COOKIE_NAME]["domain"] = host.split(":")[
                    0
                ]
        return response


class BasketOwnerHandoffMiddleware(MiddlewareMixin):
    """
    Refuse to serve a cart that belongs to someone other than the caller.

    Defence in depth for hq#12763.  Learn fills the basket over MITx Online's
    API on Learn's own domain -- where the gateway session is Learn's, and
    correct -- then sends the browser here, where the gateway session is a
    separate cookie on a separate parent domain and may still name whoever used
    this browser previously.  Learn therefore passes the id of the basket it just
    filled, and this compares it against the basket the session it arrived with
    actually owns.

    On a mismatch the browser is bounced through ``switch-session``, which
    discards the stale gateway session so the retry authenticates as the current
    user.  That bounce happens at most once per hand-off: if the retry still
    mismatches something other than a stale session is wrong, and looping would
    be worse than proceeding.  Proceeding is safe -- the caller sees their own
    session's cart, which is the wrong cart for whoever clicked but never a
    different person's data.

    Ordered after ``ApisixUserMiddleware`` so ``request.user`` reflects the
    gateway header rather than a possibly stale Django session.
    """

    def process_request(self, request):
        """Bounce a hand-off whose basket the caller's session does not own."""
        if not self._is_stale_handoff(request):
            return None

        query_params = request.GET.copy()
        query_params[SESSION_RESET_PARAM] = "1"
        # switch-session forwards every parameter other than `next` onto the
        # destination, so the retry arrives back here carrying the marker above.
        query_params["next"] = request.path
        return HttpResponseRedirect(
            f"{reverse('switch-session')}?{query_params.urlencode()}"
        )

    @staticmethod
    def _is_stale_handoff(request):
        """Whether this request names a basket its session does not own."""
        expected_basket_id = request.GET.get(EXPECTED_BASKET_PARAM)
        # The reset endpoint is where the fix happens; checking there would just
        # add a hop, and its session is mid-teardown anyway.  Only GET is
        # bounced: browsers reissue a redirected POST as a GET without its body,
        # and Learn's hand-off is a plain link.
        if (
            not expected_basket_id
            or request.method != "GET"
            or request.path.rstrip("/").endswith("/switch-session")
        ):
            return False

        # isascii() too: str.isdigit() accepts characters like "²" that int()
        # rejects, which would turn a crafted link into a 500 on any page.  The
        # length cap does the same for int()'s 4300-digit limit; a value that
        # fits but exceeds bigint matches nothing, since Django turns an
        # out-of-range integer lookup into an empty result.
        if not (
            expected_basket_id.isascii()
            and expected_basket_id.isdigit()
            and len(expected_basket_id) <= MAX_BASKET_ID_DIGITS
        ):
            log.warning(
                "Ignoring malformed %s query param: %s",
                EXPECTED_BASKET_PARAM,
                expected_basket_id,
            )
            return False

        if not request.user.is_authenticated:
            # Nothing to compare against.  The route's own auth gate decides
            # whether an anonymous caller may be here at all.
            return False

        from ecommerce.models import Basket  # noqa: PLC0415

        if Basket.objects.filter(
            user=request.user, id=int(expected_basket_id)
        ).exists():
            return False

        if request.GET.get(SESSION_RESET_PARAM):
            log.warning(
                "Basket %s still not owned by %s after a session reset; "
                "serving this session's own cart instead of bouncing again.",
                expected_basket_id,
                request.user.global_id,
            )
            return False

        return True
