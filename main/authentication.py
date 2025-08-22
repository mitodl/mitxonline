"""Custom authentication handlers for DRF."""

from rest_framework.authentication import SessionAuthentication


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """
    Authentication handler that ignores CSRF.

    Otherwise, SessionAuthentication will enforce CSRF check, even if you tell
    it not to.
    """

    def enforce_csrf(self, request):  # noqa: ARG002
        """No-op CSRF enforcement"""

        return
