"""Internal-only views for courses."""

from django.contrib.contenttypes.models import ContentType
from django.db.models import Exists, OuterRef, Prefetch
from prefetch import PrefetchOption
from rest_framework import viewsets
from rest_framework_api_key.permissions import HasAPIKey

from courses.models import (
    Course,
    CourseRun,
    Program,
)
from courses.permissions import IsEtlUser
from courses.serializers.internal import IngestibleCourseWithCourseRunsSerializer
from courses.utils import live_certificate_page_exists
from courses.views.utils import Pagination
from ecommerce.models import Product
from openedx.constants import EDX_ENROLLMENT_VERIFIED_MODE


class IngestibleCourseViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Largely a copy of the v2 CourseViewSet, but with changes for ETL processes.

    The shape of the data returned should match the v2 CourseViewSet for the most
    part, but we won't support lookups or filtering or anything and the prefetch
    setup will be reduced (since this won't have to care about what the requesting
    user's contracts are for instance).
    """

    pagination_class = Pagination
    permission_classes = [
        HasAPIKey | IsEtlUser,
    ]
    serializer_class = IngestibleCourseWithCourseRunsSerializer

    def get_queryset(self):
        """Get the queryset, with a bunch of prefetching for related data."""

        queryset = Course.objects.select_related("page")
        # Use Prefetch for reverse GenericRelation (products on CourseRun)
        # 1. Get the ContentType object for the CourseRun model
        courserun_content_type = ContentType.objects.get_for_model(CourseRun)
        # 2. Create a Prefetch object to specify the queryset for the 'tags' relation
        # This internal queryset only fetches products related to the CourseRun content type
        courserun_product_queryset = Product.objects.filter(
            content_type=courserun_content_type
        )
        # 3. Use prefetch_related on main queryset, referencing the reverse relation's name (e.g., 'products')
        products_prefetch = Prefetch(
            "products",
            queryset=courserun_product_queryset,
            to_attr="prefetched_products",
        )
        modes_prefetch = Prefetch(
            "enrollment_modes",
            to_attr="prefetched_enrollment_modes",
        )
        course_runs_prefetch = Prefetch(
            "courseruns",
            queryset=CourseRun.all_objects.order_by("id").prefetch_related(
                modes_prefetch, products_prefetch
            ),
            to_attr="prefetched_courseruns",
        )
        dated_runs_prefetch = Prefetch(
            "courseruns",
            queryset=CourseRun.all_objects.enrollable().filter(is_self_paced=False),
            to_attr="prefetched_dated_courseruns",
        )
        queryset = queryset.prefetch_related(
            "departments",
            "in_programs",
            course_runs_prefetch,
            dated_runs_prefetch,
        )
        # Only a boolean is ever read from this (CourseSerializer.
        # get_certificate_available), so Exists() beats an aggregate - no
        # GROUP BY on the main query or on the paginator's COUNT. all_objects
        # keeps this view's ETL semantics, which include source runs.
        queryset = queryset.annotate(
            has_verified_courserun=Exists(
                CourseRun.all_objects.filter(
                    course_id=OuterRef("pk"),
                    enrollment_modes__mode_slug=EDX_ENROLLMENT_VERIFIED_MODE,
                )
            ),
            has_live_certificate_page=live_certificate_page_exists(),
        )
        queryset = queryset.prefetch(
            "financial_assistance_form_url",
            PrefetchOption(
                "programs",
                queryset=Program.objects.filter(
                    live=True,
                    page__live=True,
                ).only("id", "readable_id", "title", "display_mode", "program_type"),
            ),
        )

        return queryset.order_by("title").distinct()
