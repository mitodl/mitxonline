"""
Views for Wagtail API
"""

from django.db.models import F
from rest_framework.response import Response
from wagtail.api.v2.views import PagesAPIViewSet

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

    def get_queryset(self):
        """
        Returns the queryset for the API viewset, with additional annotations
        for annotation_key based on the page type.
        """
        queryset = super().get_queryset()
        annotation_map = {
            "cms.coursepage": "course",
            "cms.programpage": "program",
        }

        model_type = self.request.GET.get("type", "").lower()
        annotation_key = self.request.GET.get("annotation", "readable_id")

        if model_type in annotation_map:
            queryset = queryset.annotate(
                **{annotation_key: F(f"{annotation_map[model_type]}__{annotation_key}")}
            )

        queryset = queryset.exclude(content_type__model__in=[
            "organizationindexpage",
            "organizationpage",
            "contractpage",
        ])

        if model_type and model_type == "cms.programpage":
            queryset = queryset.filter(program__b2b_only=False)

        if model_type and model_type == "cms.coursepage":
            queryset = queryset.filter(include_in_learn_catalog=True)

        return queryset

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
