"""Tests for OpenAPI schema generation hooks"""

import pytest
from django.conf import settings
from drf_spectacular.generators import SchemaGenerator

WAGTAIL_TYPE_FILTER_PATHS = [
    "/api/v2/pages/?fields=*&type=cms.certificatepage",
    "/api/v2/pages/?fields=*&type=cms.coursepage",
    "/api/v2/pages/?fields=*&type=cms.programpage",
]


@pytest.fixture(scope="module")
def schemas(django_db_setup, django_db_blocker):
    """
    Every version's schema, generated the way the spec files are.

    Module-scoped because generation is slow, which rules out the function
    -scoped `db` fixture; unblock explicitly instead since serializer
    introspection reads the database.
    """
    with django_db_blocker.unblock():
        return {
            version: SchemaGenerator(
                urlconf="main.urls", api_version=version
            ).get_schema(request=None, public=True)
            for version in settings.REST_FRAMEWORK["ALLOWED_VERSIONS"]
        }


def test_wagtail_type_filters_present_in_v2(schemas):
    """
    Wagtail serves all page types from /api/v2/pages/ discriminated by ?type=,
    so each type filter is published as its own operation keyed by query string.
    """
    paths = schemas["v2"]["paths"]
    missing = [p for p in WAGTAIL_TYPE_FILTER_PATHS if p not in paths]
    assert not missing, f"missing Wagtail type-filter operations from v2: {missing}"


def test_wagtail_type_filter_operation_ids_are_path_derived(schemas):
    """
    Generated clients are built against these ids, so they must stay derived
    from the path rather than being given an explicit operation_id.
    """
    paths = schemas["v2"]["paths"]
    assert [paths[p]["get"]["operationId"] for p in WAGTAIL_TYPE_FILTER_PATHS] == [
        "pages_?fields=*&type=cms.certificatepage_retrieve",
        "pages_?fields=*&type=cms.coursepage_retrieve",
        "pages_?fields=*&type=cms.programpage_retrieve",
    ]


def test_wagtail_type_filters_reference_per_type_schemas(schemas):
    """Each type filter documents its own concrete response shape."""
    paths = schemas["v2"]["paths"]
    components = schemas["v2"]["components"]["schemas"]
    for path, component in zip(
        WAGTAIL_TYPE_FILTER_PATHS,
        ["CertificatePageList", "CoursePageList", "ProgramPageList"],
    ):
        response = paths[path]["get"]["responses"]["200"]["content"]
        assert response["application/json"]["schema"]["$ref"].endswith(f"/{component}")
        assert component in components


def test_wagtail_type_filters_absent_from_other_versions(schemas):
    """
    These are v2 operations. They are injected by a preprocessing hook rather
    than routed, so only SchemaOnlyV2Versioning keeps them out of every other
    spec - without it they leak into all of them.
    """
    leaked = {
        version: [p for p in WAGTAIL_TYPE_FILTER_PATHS if p in schema["paths"]]
        for version, schema in schemas.items()
        if version != "v2"
    }
    assert not any(leaked.values()), f"Wagtail type filters leaked: {leaked}"


def test_real_wagtail_pages_endpoints_still_documented(schemas):
    """
    The type filters are additions, not replacements - the real routed
    endpoints are served by WagtailPagesAPIViewSet and must stay documented.
    """
    paths = schemas["v2"]["paths"]
    assert paths["/api/v2/pages/"]["get"]["operationId"] == "pages_list"
    assert paths["/api/v2/pages/{id}/"]["get"]["operationId"] == "pages_retrieve"
