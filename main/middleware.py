"""Common mitx_online middleware"""
from django.utils.deprecation import MiddlewareMixin


class CachelessAPIMiddleware(MiddlewareMixin):
    """Add Cache-Control header to API responses"""

    def process_response(self, request, response):
        """Add a Cache-Control header to an API response"""
        if request.path.startswith("/api/") or request.path.startswith("/courses/"):
            response["Cache-Control"] = "private, no-store"
        return response
