"""Common mitx_online middleware"""

import logging
import uuid
from urllib.parse import urlparse

from django.conf import settings
from django.http import HttpResponseRedirect
from django.middleware.csrf import CsrfViewMiddleware
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
        response = super().process_response(request, response)
        # Origin is the page's origin and browsers send it on every cross-origin
        # fetch/XHR regardless of the page's referrer policy. Referer is subject
        # to that policy and may be absent, in which case the cookie keeps
        # CSRF_COOKIE_DOMAIN and a response from any other host cannot set it.
        # Referer is only a fallback for clients that send no Origin.
        source = request.headers.get("origin") or request.headers.get("referer")
        if settings.CSRF_COOKIE_NAME in response.cookies and source:
            host = urlparse(source).netloc
            csrf_trusted_hosts = []
            for origin in getattr(settings, "CSRF_TRUSTED_ORIGINS", []):
                parsed_origin = urlparse(origin)
                if parsed_origin.netloc:
                    csrf_trusted_hosts.append(parsed_origin.netloc)
            if host in csrf_trusted_hosts:
                response.cookies[settings.CSRF_COOKIE_NAME]["domain"] = host.split(":")[
                    0
                ]
        return response
