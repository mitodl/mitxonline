"""
Views for Wagtail API Schema
"""

from cms.wagtail_apit.schema.serializers import (
    CertificatePageListSerializer,
    CoursePageListSerializer,
    PageListSerializer,
    ProgramPageListSerializer,
)
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from main.versioning import V2Versioning
from rest_framework.response import Response
from rest_framework.views import APIView


class WagtailPagesSchemaView(APIView):
    """
    View for listing all Wagtail pages with schema documentation.
    """

    versioning_class = V2Versioning

    @extend_schema(
        summary="List all Wagtail Pages",
        description="Returns pages of all types",
        operation_id="pages_list",
        parameters=[
            OpenApiParameter(
                name="type",
                required=False,
                type=str,
                description="Filter by Wagtail page type",
            ),
            OpenApiParameter(
                name="fields",
                required=False,
                type=str,
                description="Specify fields (e.g. `*`)",
            ),
        ],
        responses=PageListSerializer,
    )
    def get(self, request, *args, **kwargs):  # noqa: ARG002
        # You can return a dummy response or redirect to actual Wagtail logic
        return Response(
            {
                "meta": {
                    "total_count": 0,
                },
                "items": [],
            }
        )


class WagtailCertificatePagesSchemaView(APIView):
    """
    View for listing all Certificate Pages with schema documentation.
    """

    versioning_class = V2Versioning

    @extend_schema(
        summary="List all Certificate Pages",
        description="Returns pages of type cms.CertificatePage",
        responses=CertificatePageListSerializer,
    )
    def get(self, request, *args, **kwargs):  # noqa: ARG002
        # You can return a dummy response or redirect to actual Wagtail logic
        return Response(
            {
                "meta": {
                    "total_count": 0,
                },
                "items": [],
            }
        )


class WagtailCoursePagesSchemaView(APIView):
    """
    View for listing all Course Pages with schema documentation.
    """

    versioning_class = V2Versioning

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
        # You can return a dummy response or redirect to actual Wagtail logic
        return Response(
            {
                "meta": {
                    "total_count": 0,
                },
                "items": [],
            }
        )


class WagtailProgramPagesSchemaView(APIView):
    """
    View for listing all Program Pages with schema documentation.
    """

    versioning_class = V2Versioning

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
        # You can return a dummy response or redirect to actual Wagtail logic
        return Response(
            {
                "meta": {
                    "total_count": 0,
                },
                "items": [],
            }
        )


class WagtailPagesRetrieveSchemaView(APIView):
    """
    View for retrieving details of a specific Wagtail page with schema documentation.
    """

    versioning_class = V2Versioning

    @extend_schema(
        summary="Get Wagtail Page Details",
        description="Returns details of a specific Wagtail page by ID",
        operation_id="pages_retrieve",
        parameters=[
            OpenApiParameter(
                name="id",
                type=int,
                location=OpenApiParameter.PATH,
                required=True,
                description="ID of the Wagtail page",
            ),
            OpenApiParameter(
                name="revision_id",
                required=False,
                type=int,
                description="Optional certificate revision ID to retrieve a specific revision of the certificate page",
            ),
        ],
        responses={
            200: OpenApiResponse(
                response={
                    "oneOf": [
                        {"$ref": "#/components/schemas/CoursePageItem"},
                        {"$ref": "#/components/schemas/ProgramPageItem"},
                        {"$ref": "#/components/schemas/CertificatePage"},
                        {"$ref": "#/components/schemas/Page"},
                    ]
                },
                description="Returns a page of any known Wagtail page type",
            )
        },
    )
    def get(self, request, id, *args, **kwargs):  # noqa: ARG002, A002
        return Response(
            {
                "id": id,
                "title": "Sample Page",
                "meta": {
                    "total_count": 1,
                },
            }
        )
