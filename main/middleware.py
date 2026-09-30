"""Common mitx_online middleware"""

import logging
import uuid
from urllib.parse import urlparse

from django.conf import settings
from django.http import HttpResponseRedirect
from django.middleware.csrf import CsrfViewMiddleware, get_token
from django.utils.deprecation import MiddlewareMixin

log = logging.getLogger(__name__)

ANONYMOUS_BASKET_HANDOFF_PARAM = "anonymous_basket_id"


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
