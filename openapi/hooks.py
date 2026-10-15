"""Extensions for OpenAPI schema"""

import re
from types import SimpleNamespace

from django.core.exceptions import ImproperlyConfigured
from django.urls import URLResolver, get_resolver
from rest_framework.views import APIView

from main.versioning import NoVersioning
from openapi.exceptions import EnumDescriptionError

ENUM_DESCRIPTION_RE = re.compile(r"\w*\*\s`(?P<key>.*)`\s\-\s(?P<description>.*)")


def _iter_described_enums(schema, *, name=None, is_root=True):
    """
    Create an iterator over all enums with descriptions
    """
    if is_root:
        for item_name, item in schema.items():
            yield from _iter_described_enums(item, name=item_name, is_root=False)
    elif isinstance(schema, list):
        for item in schema:
            yield from _iter_described_enums(item, name=name, is_root=is_root)
    elif isinstance(schema, dict):
        if "enum" in schema and "description" in schema:
            yield name, schema

        yield from _iter_described_enums(
            schema.get("properties", []), name=name, is_root=is_root
        )
        yield from _iter_described_enums(
            schema.get("oneOf", []), name=name, is_root=is_root
        )
        yield from _iter_described_enums(
            schema.get("allOf", []), name=name, is_root=is_root
        )
        yield from _iter_described_enums(
            schema.get("anyOf", []), name=name, is_root=is_root
        )


def postprocess_x_enum_descriptions(result, generator, request, public):  # noqa: ARG001
    """
    Take the drf-spectacular generated descriptions and
    puts it into the x-enum-descriptions property.
    """

    # your modifications to the schema in parameter result
    schemas = result.get("components", {}).get("schemas", {})

    for name, schema in _iter_described_enums(schemas):
        lines = schema["description"].splitlines()
        descriptions_by_value = {}
        for line in lines:
            match = ENUM_DESCRIPTION_RE.match(line)
            if match is None:
                continue

            key = match["key"]
            description = match["description"]

            # sometimes there are descriptions for empty values
            # that aren"t present in `"enums"`
            # regex keys are always strings
            enums_as_str = [str(e) for e in schema["enum"]]
            if key in enums_as_str:
                descriptions_by_value[key] = description

        if len(descriptions_by_value.values()) != len(schema["enum"]):
            msg = f"Unable to find descriptions for all enum values: {name}"
            raise EnumDescriptionError(msg)

        if descriptions_by_value:
            schema["x-enum-descriptions"] = [
                descriptions_by_value[str(value)] for value in schema["enum"]
            ]

    return result


def exclude_paths_hook(endpoints, **kwargs):  # noqa: ARG001
    # List of path prefixes to exclude
    EXCLUDED_PATHS = [
        "/api/hubspot_sync/",
        "/api/flexible_pricing/",
        "/api/cms/",
        "/cms/",
        "/api/login/",
        "/api/register/",
        "/api/password_reset/",
        "/api/set_password/",
        "/api/auths/",
        "/.well-known/openid-configuration",
        "/api/countries/",
        "/api/users/",
        "/api/change-emails/",
        "/api/user_search/",
        "/api/partnerschools/",
        "/api/v1/partnerschools/",
        "/api/products/",
        "/api/checkout/",
        "/api/discounts/",
        "/api/baskets/",
        "/api/orders/",
        "/api/checkout/",
        "/api/instructor/",
        "/api/v0/checkout/",
        "/api/v2/images/",
        "/api/v2/documents/",
        "/api/internal/",
        "/api/v0/b2b/webhook",
        "/webhook/",
        # Learner records: unversioned paths under /api/records/, consumed only by
        # our own hand-written redux-query code, which doesn't read the spec.
        "/api/records/",
        # Enrollment form-post/redirect target, outside the /api/ REST surface.
        "/enrollments/",
    ]

    # Filter out endpoints whose paths start with any of the excluded prefixes
    return [
        (path, path_regex, method, callback)
        for (path, path_regex, method, callback) in endpoints
        if not any(path.startswith(prefix) for prefix in EXCLUDED_PATHS)
    ]


def iter_drf_routes(resolver=None, prefix="", namespaces=()):
    """
    Yield (namespace, path, callback) for every DRF view in the URLconf, where
    `namespace` is the colon-joined instance namespace a request to that route
    resolves to - the value NamespaceVersioning reads the version from.
    """
    for pattern in (resolver or get_resolver()).url_patterns:
        if isinstance(pattern, URLResolver):
            yield from iter_drf_routes(
                pattern,
                prefix + str(pattern.pattern),
                namespaces + ((pattern.namespace,) if pattern.namespace else ()),
            )
            continue

        callback = pattern.callback
        view_class = getattr(callback, "cls", None) or getattr(
            callback, "view_class", None
        )
        if isinstance(view_class, type) and issubclass(view_class, APIView):
            yield ":".join(namespaces), prefix + str(pattern.pattern), callback


def require_api_version_hook(endpoints, **kwargs):  # noqa: ARG001
    """
    Fail schema generation for any endpoint that resolves to no API version.

    Schema generation matches views on version, so a view whose version is
    None is silently missing from every spec, and a view with
    `versioning_class = None` skips the match and lands in every spec. Each
    view must get a version from its namespace or its versioning_class, or
    say NoVersioning.

    Runs after exclude_paths_hook, so it checks exactly the endpoints that
    reach schema generation. It runs whenever a schema is generated
    (generate_openapi_spec in CI, and the /api/vN/schema/ views), never on
    an API request.
    """
    # Keyed by route, not callback: one view can be mounted under several
    # namespaces (flexible pricing at /api/ and /api/v0/). drf-spectacular
    # builds path_regex the same way iter_drf_routes builds its path.
    namespaces = {route: namespace for namespace, route, _ in iter_drf_routes()}
    unversioned = []
    for path, path_regex, method, callback in endpoints:
        versioning_class = callback.initkwargs.get(
            "versioning_class", callback.cls.versioning_class
        )
        if versioning_class is not None and issubclass(versioning_class, NoVersioning):
            continue
        request = SimpleNamespace(
            resolver_match=SimpleNamespace(namespace=namespaces.get(path_regex, ""))
        )
        if (
            versioning_class is None
            or versioning_class().determine_version(request) is None
        ):
            unversioned.append(f"{method} {path}")

    if unversioned:
        msg = (
            "These endpoints resolve to no API version, so they would be missing "
            "from every OpenAPI spec (or, with versioning_class = None, in every "
            "one). Give each view a versioning_class: "
            "V0Versioning or V2Versioning to put it in a spec, or NoVersioning "
            "to keep it out of all of them (needed even with "
            "extend_schema(exclude=True), which drf-spectacular applies after "
            "this check).\n  " + "\n  ".join(unversioned)
        )
        raise ImproperlyConfigured(msg)
    return endpoints


def insert_wagtail_pages_schema(endpoints, **kwargs):  # noqa: ARG001
    """
    Publish one operation per Wagtail page type filter.

    Wagtail serves every page type from `/api/v2/pages/` discriminated by a
    `?type=` query parameter, and OpenAPI cannot key an operation on a query
    string - so these operations are appended here rather than routed. The
    views carry `SchemaOnlyV2Versioning`, which keeps them in v2.yaml only.

    See `cms.wagtail_api.schema.views` for why the paths look like this and
    why the operation ids must stay path-derived.
    """
    from cms.wagtail_api.schema.views import (  # noqa: PLC0415
        WagtailCertificatePagesSchemaView,
        WagtailCoursePagesSchemaView,
        WagtailProgramPagesSchemaView,
    )

    type_filters = [
        ("cms.certificatepage", WagtailCertificatePagesSchemaView),
        ("cms.coursepage", WagtailCoursePagesSchemaView),
        ("cms.programpage", WagtailProgramPagesSchemaView),
    ]

    for page_type, view_class in type_filters:
        path = f"/api/v2/pages/?fields=*&type={page_type}"
        callback = view_class.as_view()
        # drf-spectacular reads `.cls` off the callback to build the view it
        # introspects; as_view() only sets `.cls` for DRF's own routers.
        callback.cls = view_class
        endpoints.append((path, f"^{path.lstrip('/')}$", "GET", callback))

    return endpoints
