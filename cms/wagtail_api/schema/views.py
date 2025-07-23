"""
Views for Wagtail API Schema
"""

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    CertificatePageListSerializer,
    CoursePageListSerializer,
    PageListSerializer,
)


class WagtailPagesSchemaView(APIView):
    """
    View for listing all Wagtail pages with schema documentation.
    """

    @extend_schema(
        summary="List all Wagtail Pages",
        description="Returns pages of all types",
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

    @extend_schema(
        summary="List all Course Pages",
        description="Returns pages of type cms.CoursePage",
        responses=CoursePageListSerializer,
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
