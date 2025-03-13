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
        "/api/v0/baskets/",
        "/api/v0/discounts/",
        "/api/v0/flexible_pricing/",
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
        "/api/v0/products/",
        "/api/products/",
        "/api/checkout/",
        "/api/discounts/",
        "/api/baskets/",
        "/api/orders/",
        "/api/checkout/",
        "/api/instructor/",
        "/api/v0/checkout/",
        "/api/v0/orders/",
    ]

    # Filter out endpoints whose paths start with any of the excluded prefixes
    return [
        (path, path_regex, method, callback)
        for (path, path_regex, method, callback) in endpoints
        if not any(path.startswith(prefix) for prefix in EXCLUDED_PATHS)
    ]
