"""Common mitx_online middleware"""

import faulthandler
import logging
import sys
import threading
import uuid
from urllib.parse import urlparse

from django.conf import settings
from django.http import HttpResponseRedirect
from django.middleware.csrf import CsrfViewMiddleware
from django.utils.deprecation import MiddlewareMixin

log = logging.getLogger(__name__)

ANONYMOUS_BASKET_HANDOFF_PARAM = "anonymous_basket_id"


class SlowRequestWatchdogMiddleware:
    """
    Dump every thread's stack if a request runs past a threshold.

    Written as a plain callable rather than a MiddlewareMixin subclass so the
    watchdog timer is cancelled in a `finally` block -- guaranteed to run
    whether the view returns normally or raises, unlike relying on
    process_response being reached.

    Uses a per-request threading.Timer rather than
    faulthandler.dump_traceback_later: that call is a single process-global
    timer, so a second concurrent request (Granian runs multiple
    blocking_threads per worker) would silently cancel the first request's
    scheduled dump instead of adding its own. A dedicated Timer per request
    has its own independent cancel(), and the dump it triggers
    (faulthandler.dump_traceback) is a plain one-shot call that's safe to
    fire from multiple threads at once.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not settings.SLOW_REQUEST_WATCHDOG_ENABLED:
            return self.get_response(request)

        timer = threading.Timer(
            settings.SLOW_REQUEST_WATCHDOG_THRESHOLD_SECONDS,
            faulthandler.dump_traceback,
            kwargs={"file": sys.stderr, "all_threads": True},
        )
        timer.daemon = True
        timer.start()
        try:
            return self.get_response(request)
        finally:
            timer.cancel()


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
    CSRF middleware that changes the response cookie's domain property
    to match the request's host if it exists in settings.CSRF_TRUSTED_ORIGINS
    """

    def process_response(self, request, response):
        response = super().process_response(request, response)
        referrer = request.headers.get("referer", None)
        if settings.CSRF_COOKIE_NAME in response.cookies and referrer:
            parsed_referrer = urlparse(referrer)
            host = parsed_referrer.netloc
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
