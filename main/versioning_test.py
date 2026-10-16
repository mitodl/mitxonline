"""Tests for custom DRF versioning schemes"""

import pytest
from django.conf import settings

from main.versioning import FallbackNamespaceVersioning, NoVersioning
from openapi.hooks import iter_drf_routes


def test_no_drf_view_404s_on_its_namespace():
    """
    Every DRF view must resolve a version for the namespace it's actually
    mounted under.

    NamespaceVersioning raises NotFound - a 404 on real requests - when the
    resolved namespace isn't in ALLOWED_VERSIONS. Views under a namespace that
    is load-bearing for reverse() and therefore can't be a version name (b2b's
    "b2b", Wagtail's "wagtailapi:images") must use a FallbackNamespaceVersioning
    subclass or NoVersioning, neither of which raises.
    """
    allowed = set(settings.REST_FRAMEWORK["ALLOWED_VERSIONS"])
    offenders = sorted(
        {
            f"{callback.cls.__module__}.{callback.cls.__qualname__} "
            f"(namespace {namespace!r}, /{path})"
            for namespace, path, callback in iter_drf_routes()
            if namespace
            and not allowed.intersection(namespace.split(":"))
            and not (
                callback.cls.versioning_class
                and issubclass(
                    callback.cls.versioning_class,
                    (FallbackNamespaceVersioning, NoVersioning),
                )
            )
        }
    )

    assert not offenders, (
        "These DRF views resolve to a namespace that is not in ALLOWED_VERSIONS "
        "and use neither a FallbackNamespaceVersioning subclass nor NoVersioning, "
        "so they return 404 for every request:\n  " + "\n  ".join(offenders)
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
