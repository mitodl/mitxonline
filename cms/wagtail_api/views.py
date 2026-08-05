"""
Views for Wagtail API
"""

from enum import Enum

from django.db.models import F
from drf_spectacular.utils import (
    OpenApiParameter,
    PolymorphicProxySerializer,
    extend_schema,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from wagtail.api.v2.views import PagesAPIViewSet

from cms.models import CertificatePage
from cms.wagtail_api.filters import ReadableIDFilter
from cms.wagtail_api.schema.serializers import (
    CertificatePageSerializer,
    CoursePageItemSerializer,
    PageListSerializer,
    PageSerializer,
    ProgramPageItemSerializer,
)
from main.versioning import V2Versioning


class PageType(Enum):
    """
    Enumeration of Wagtail page types.
    """

    COURSE = "cms.coursepage"
    PROGRAM = "cms.programpage"
    CERTIFICATE = "cms.certificatepage"

    @classmethod
    def anonymous_access_allowed_types(cls):
        """
        Returns a list of page types that allow anonymous access.

        Returns:
            list: List of page type values that allow anonymous access.
        """
        return [cls.COURSE.value, cls.PROGRAM.value, cls.CERTIFICATE.value]


class WagtailPagesAPIViewSet(PagesAPIViewSet):
    """
    Custom API viewset for Wagtail pages with
    additional filtering and metadata fields.
    """

    versioning_class = V2Versioning

    filter_backends = [ReadableIDFilter, *PagesAPIViewSet.filter_backends]
    meta_fields = [*PagesAPIViewSet.meta_fields, "live", "last_published_at"]
    listing_default_fields = [
        *PagesAPIViewSet.listing_default_fields,
        "live",
        "last_published_at",
    ]
    known_query_parameters = PagesAPIViewSet.known_query_parameters.union(
        ["readable_id"]
    )

    def get_permissions(self):
        """
        Returns the appropriate permissions based on the 'type' query parameter.
        """
        page_type = self.request.query_params.get("type", "").lower()
        if page_type in PageType.anonymous_access_allowed_types():
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        """
        drf-spectacular's mocked schema-generation request never has
        `wagtailapi_router` set (only real requests dispatched through
        Wagtail's own router do), which the base implementation needs.
        Fall back to a plain serializer in that case - the @extend_schema
        decorators above already declare the real response shape.
        """
        if not hasattr(self.request, "wagtailapi_router"):
            return PageSerializer
        return super().get_serializer_class()

    def get_queryset(self):
        """
        Returns the queryset for the API viewset, with additional annotations
        for annotation_key based on the page type.
        """
        queryset = super().get_queryset()
        annotation_map = {
            PageType.COURSE.value: "course",
            PageType.PROGRAM.value: "program",
        }

        model_type = self.request.GET.get("type", "").lower()
        annotation_key = self.request.GET.get("annotation", "readable_id")

        if model_type in annotation_map:
            queryset = queryset.annotate(
                **{annotation_key: F(f"{annotation_map[model_type]}__{annotation_key}")}
            )

        if model_type and not self.request.user.is_authenticated:
            if model_type == PageType.PROGRAM.value:
                queryset = queryset.filter(
                    program__b2b_only=False,
                    include_in_learn_catalog=True,
                )
            elif model_type == PageType.COURSE.value:
                queryset = queryset.filter(include_in_learn_catalog=True)

        return queryset

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
    def listing_view(self, request):
        return super().listing_view(request)

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
        responses=PolymorphicProxySerializer(
            component_name="PageDetail",
            serializers=[
                CoursePageItemSerializer,
                ProgramPageItemSerializer,
                CertificatePageSerializer,
                PageSerializer,
            ],
            resource_type_field_name=None,
        ),
    )
    def detail_view(self, request, pk):  # noqa: ARG002
        """
        Returns the detail view of a page instance.

        If the instance is a CertificatePage and a revision_id is provided,
        it retrieves the specific revision of that page.
        """
        instance = self.get_object()
        if isinstance(instance, CertificatePage) and request.GET.get("revision_id"):
            revision = instance.revisions.filter(
                id=request.GET.get("revision_id")
            ).first()
            if not revision:
                return Response({"error": "Revision not found"}, status=404)
            instance = revision.as_object()
        serializer = self.get_serializer(instance)
        data = serializer.data
        return Response(data)
