"""Tests for custom DRF versioning schemes"""

import pytest
from django.conf import settings
from django.urls import URLResolver, get_resolver
from rest_framework.views import APIView

from main.versioning import FallbackNamespaceVersioning


def _drf_views_with_namespaces():
    """
    Walk the root URLconf and yield (namespace, path, view_class) for every
    DRF view, where `namespace` is the full colon-joined instance namespace.
    """

    def walk(resolver, prefix, namespaces):
        for pattern in resolver.url_patterns:
            if isinstance(pattern, URLResolver):
                yield from walk(
                    pattern,
                    prefix + str(pattern.pattern),
                    namespaces + ([pattern.namespace] if pattern.namespace else []),
                )
                continue

            callback = pattern.callback
            view_class = getattr(callback, "cls", None) or getattr(
                callback, "view_class", None
            )
            if isinstance(view_class, type) and issubclass(view_class, APIView):
                yield (
                    ":".join(namespaces),
                    prefix + str(pattern.pattern),
                    view_class,
                )

    yield from walk(get_resolver(), "", [])


def test_no_drf_view_404s_on_its_namespace():
    """
    Every DRF view must resolve a version for the namespace it's actually
    mounted under.

    NamespaceVersioning raises NotFound - a 404 on real requests - when the
    resolved namespace isn't in ALLOWED_VERSIONS. Views under a namespace that
    is load-bearing for reverse() and therefore can't be a version name (b2b's
    "b2b", Wagtail's "wagtailapi:images") must use a FallbackNamespaceVersioning
    subclass so they resolve a version instead of 404ing.
    """
    allowed = set(settings.REST_FRAMEWORK["ALLOWED_VERSIONS"])
    offenders = sorted(
        {
            f"{view_class.__module__}.{view_class.__qualname__} "
            f"(namespace {namespace!r}, /{path})"
            for namespace, path, view_class in _drf_views_with_namespaces()
            if namespace
            and not allowed.intersection(namespace.split(":"))
            and not (
                view_class.versioning_class
                and issubclass(view_class.versioning_class, FallbackNamespaceVersioning)
            )
        }
    )

    assert not offenders, (
        "These DRF views resolve to a namespace that is not in ALLOWED_VERSIONS "
        "and do not use a FallbackNamespaceVersioning subclass, so they return "
        "404 for every request:\n  " + "\n  ".join(offenders)
    )


@pytest.mark.parametrize(
    ("namespace", "expected"),
    [
        ("v0", "v0"),
        ("b2b", None),
        ("wagtailapi:images", None),
        ("", None),
    ],
)
def test_fallback_versioning_never_raises(mocker, rf, namespace, expected):
    """
    FallbackNamespaceVersioning returns default_version instead of raising for
    namespaces that aren't allowed versions.
    """
    request = rf.get("/")
    request.resolver_match = mocker.Mock(namespace=namespace)

    assert FallbackNamespaceVersioning().determine_version(request) == expected
