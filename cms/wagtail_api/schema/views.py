"""
Schema-only views for the Wagtail pages API type filters.

Wagtail serves every page type from a single endpoint, `/api/v2/pages/`,
discriminated by a `?type=` query parameter. Clients rely on knowing the
concrete response shape per type, which a single operation on the real
path cannot express, so each type filter is published as its own
operation keyed by the full query string.

OpenAPI has no way to key an operation on a query string, so these are
injected as extra endpoints by `openapi.hooks.insert_wagtail_pages_schema`
rather than routed. Nothing dispatches to them at request time - the real
viewset is `cms.wagtail_api.views.WagtailPagesAPIViewSet`, which serves
`/api/v2/pages/` and `/api/v2/pages/{id}/`.

Do not set `operation_id` here: the generated ids are derived from the
path (e.g. `pages_?fields=*&type=cms.coursepage_retrieve`) and downstream
generated clients are built against those names.
"""

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from main.versioning import SchemaOnlyV2Versioning

from .serializers import (
    CertificatePageListSerializer,
    CoursePageListSerializer,
    ProgramPageListSerializer,
)

EMPTY_PAGE_LIST = {"meta": {"total_count": 0}, "items": []}


class WagtailCertificatePagesSchemaView(APIView):
    """
    Documents `/api/v2/pages/?fields=*&type=cms.certificatepage`.
    """

    versioning_class = SchemaOnlyV2Versioning

    @extend_schema(
        summary="List all Certificate Pages",
        description="Returns pages of type cms.CertificatePage",
        responses=CertificatePageListSerializer,
    )
    def get(self, request, *args, **kwargs):  # noqa: ARG002
        return Response(EMPTY_PAGE_LIST)


class WagtailCoursePagesSchemaView(APIView):
    """
    Documents `/api/v2/pages/?fields=*&type=cms.coursepage`.
    """

    versioning_class = SchemaOnlyV2Versioning

    @extend_schema(
        summary="List all Course Pages",
        description="Returns pages of type cms.CoursePage",
        responses=CoursePageListSerializer,
        parameters=[
            OpenApiParameter(
                name="readable_id",
                required=False,
                type=str,
                description="filter by course readable_id",
            ),
        ],
    )
    def get(self, request, *args, **kwargs):  # noqa: ARG002
        return Response(EMPTY_PAGE_LIST)


class WagtailProgramPagesSchemaView(APIView):
    """
    Documents `/api/v2/pages/?fields=*&type=cms.programpage`.
    """

    versioning_class = SchemaOnlyV2Versioning

    @extend_schema(
        summary="List all Program Pages",
        description="Returns pages of type cms.ProgramPage",
        responses=ProgramPageListSerializer,
        parameters=[
            OpenApiParameter(
                name="readable_id",
                required=False,
                type=str,
                description="filter by program readable_id",
            ),
        ],
    )
    def get(self, request, *args, **kwargs):  # noqa: ARG002
        return Response(EMPTY_PAGE_LIST)
