"""Common mitx_online middleware"""

from urllib.parse import urlparse

from django.conf import settings
from django.middleware.csrf import CsrfViewMiddleware
from django.utils.deprecation import MiddlewareMixin

SUBDOMAIN_THRESHOLD = 3


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


class HostBasedCSRFMiddleware(CsrfViewMiddleware):
    """
    CSRF middleware that changes the response cookie's domain property
    to match the request's host if it exists in settings.CSRF_TRUSTED_ORIGINS
    """

    def process_response(self, request, response):
        response = super().process_response(request, response)
        referrer = request.META.get('HTTP_REFERER', None)
        if settings.CSRF_COOKIE_NAME in response.cookies and referrer:
            parsed_referrer = urlparse(referrer)
            host = parsed_referrer.netloc
            csrf_trusted_hosts = []
            for origin in getattr(settings, "CSRF_TRUSTED_ORIGINS", []):
                parsed_origin = urlparse(origin)
                if parsed_origin.netloc:
                    csrf_trusted_hosts.append(parsed_origin.netloc)
            if host in csrf_trusted_hosts:
                host_parts = host.split(".")
                # Only wildcard on second tier subdomains (3 parts or more)
                # e.g. "api.learn.mit.edu" -> ".learn.mit.edu"
                if len(host_parts) > SUBDOMAIN_THRESHOLD:
                    parent_domain = "." + ".".join(host_parts[1:])
                else:
                    parent_domain = host
                response.cookies[settings.CSRF_COOKIE_NAME]["domain"] = parent_domain
        return response
