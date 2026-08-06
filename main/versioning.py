"""Custom DRF versioning schemes."""

from rest_framework import exceptions
from rest_framework.versioning import NamespaceVersioning, URLPathVersioning


class FallbackNamespaceVersioning(NamespaceVersioning):
    """
    Like NamespaceVersioning, but falls back to `default_version`
    instead of raising NotFound when the resolved namespace doesn't
    match any allowed version.

    This is the project-wide default (see DEFAULT_VERSIONING_CLASS).
    Plain NamespaceVersioning would 404 every DRF view whose namespace
    isn't in ALLOWED_VERSIONS - and plenty of ours aren't, because a
    namespace is load-bearing for `reverse()` (b2b's "b2b", Wagtail's
    "wagtailapi:images") and can't be renamed to a version. With
    `default_version` left as DEFAULT_VERSION (None), those views get
    `request.version = None`, which is exactly what they got before
    versioning was switched on, and nothing reads request.version.

    Subclass it with an explicit `default_version` to attribute such a
    view to a spec, since schema generation matches on version and None
    matches nothing.
    """

    def determine_version(self, request, *args, **kwargs):
        try:
            return super().determine_version(request, *args, **kwargs)
        except exceptions.NotFound:
            return self.default_version


class V0Versioning(FallbackNamespaceVersioning):
    """
    b2b's views live under namespace "b2b" (relied on by reverse()
    calls throughout its test suite), not "v0". Used directly on b2b's
    view classes so schema generation attributes them to v0 without
    touching that namespace.
    """

    default_version = "v0"


class V2Versioning(FallbackNamespaceVersioning):
    """
    Wagtail's own router puts its real pages viewset under a namespace
    we don't control (`wagtailapi:pages`), which will never be in
    ALLOWED_VERSIONS.
    """

    default_version = "v2"


class SchemaOnlyV2Versioning(URLPathVersioning):
    """
    Pins a synthetic, schema-only view to v2.

    For operations injected by a drf-spectacular preprocessing hook at a
    "path" that is not a real URL - the Wagtail pages type filters, whose
    path carries a query string. A NamespaceVersioning subclass is wrong
    here: drf-spectacular resolves the path against the URLconf to find
    the namespace, and a non-URL path raises Resolver404, which emits a
    spectacular error and fails `--fail-on-warn`. URLPathVersioning skips
    that resolution, and reporting `default_version` unconditionally puts
    the operation in exactly one spec.

    These views are never routed, so this has no request-time meaning.
    """

    default_version = "v2"

    def determine_version(self, request, *args, **kwargs):  # noqa: ARG002
        return self.default_version
