"""Common mitx_online middleware"""
from django.utils.deprecation import MiddlewareMixin


class CachelessAPIMiddleware(MiddlewareMixin):
    """Add Cache-Control header to API responses"""

    def process_response(self, request, response):
        """Add a Cache-Control header to an API response"""
        if request.path.startswith("/api/"):
            response["Cache-Control"] = "private, no-store"
        elif not request.user.is_anonymous and request.path.startswith("/courses/course"):
            response["Cache-Control"] = "no-store"
        return response
