"""Custom DRF versioning schemes."""

from rest_framework import exceptions
from rest_framework.versioning import NamespaceVersioning


class _FallbackNamespaceVersioning(NamespaceVersioning):
    """
    Like NamespaceVersioning, but falls back to `default_version`
    instead of raising NotFound when the resolved namespace doesn't
    match any allowed version. Real request-time behavior is
    unaffected (nothing reads request.version today) - this exists for
    views whose real, load-bearing namespace (used elsewhere for
    `reverse()`) can't be changed to match a version namespace, so
    schema generation needs an explicit per-view override instead.
    """

    def determine_version(self, request, *args, **kwargs):
        try:
            return super().determine_version(request, *args, **kwargs)
        except exceptions.NotFound:
            return self.default_version


class V0Versioning(_FallbackNamespaceVersioning):
    """
    b2b's views live under namespace "b2b" (relied on by reverse()
    calls throughout its test suite), not "v0". Used directly on b2b's
    view classes so schema generation attributes them to v0 without
    touching that namespace.
    """

    default_version = "v0"


class V2Versioning(_FallbackNamespaceVersioning):
    """
    Wagtail's own router puts its real pages viewset under a namespace
    we don't control (`wagtailapi:pages`), which will never be in
    ALLOWED_VERSIONS.
    """

    default_version = "v2"
