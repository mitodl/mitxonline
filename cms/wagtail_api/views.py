"""
Views for Wagtail API
"""

from django.db.models import F
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from wagtail.api.v2.views import PagesAPIViewSet
from wagtail.models import Revision

from cms.models import CertificatePage
from cms.wagtail_api.filters import ReadableIDFilter


class WagtailPagesAPIViewSet(PagesAPIViewSet):
    """
    Custom API viewset for Wagtail pages with
    additional filtering and metadata fields.
    """

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
    permission_classes = (AllowAny,)

    def get_queryset(self):
        """
        Returns the queryset for the API viewset, with additional annotations
        for annotation_key based on the page type.
        """
        queryset = super().get_queryset()
        annotation_map = {
            "cms.CoursePage": "course",
            "cms.ProgramPage": "program",
        }

        model_type = self.request.GET.get("type")
        annotation_key = self.request.GET.get("annotation", "readable_id")

        if model_type in annotation_map:
            queryset = queryset.annotate(
                **{annotation_key: F(f"{annotation_map[model_type]}__{annotation_key}")}
            )

        return queryset

    def detail_view(self, request, pk):  # noqa: ARG002
        """
        Returns the detail view of a page instance.

        If the instance is a CertificatePage and a revision_id is provided,
        it retrieves the specific revision of that page.
        """
        instance = self.get_object()
        if isinstance(instance, CertificatePage) and request.GET.get("revision_id"):
            try:
                instance = Revision.objects.get(
                    id=request.GET.get("revision_id")
                ).as_object()
            except Revision.DoesNotExist:
                return Response({"error": "Revision not found"}, status=404)
        serializer = self.get_serializer(instance)
        data = serializer.data
        return Response(data)
