"""Extensions for OpenAPI schema"""

import re

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
