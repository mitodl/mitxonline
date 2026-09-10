"""Internal-only views for courses."""

from django.contrib.contenttypes.models import ContentType
from django.db.models import Prefetch
from prefetch import PrefetchOption
from rest_framework import viewsets
from rest_framework_api_key.permissions import HasAPIKey

from courses.models import (
    Course,
    CourseRun,
    CoursesTopic,
    Program,
)
from courses.permissions import IsEtlUser
from courses.serializers.internal import IngestibleCourseWithCourseRunsSerializer
from courses.utils import live_certificate_page_exists, verified_courserun_exists
from courses.views.utils import Pagination
from ecommerce.models import Product


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

        # page__feature_image matches the v2 CourseViewSet: CoursePageSerializer
        # .get_feature_image_src dereferences it for every serialized course.
        queryset = Course.objects.select_related("page", "page__feature_image")
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
        # No to_attr: this has to land in the plain "courseruns" prefetch cache,
        # because Course.first_unexpired_run reads self.courseruns.all(). Under a
        # to_attr-only prefetch that cache stays empty and every serialized
        # course issues its own query. IngestibleCourseWithCourseRunsSerializer
        # already falls back to instance.courseruns, so nothing else changes.
        course_runs_prefetch = Prefetch(
            "courseruns",
            queryset=CourseRun.all_objects.order_by("id").prefetch_related(
                modes_prefetch, products_prefetch
            ),
        )
        dated_runs_prefetch = Prefetch(
            "courseruns",
            queryset=CourseRun.all_objects.enrollable().filter(is_self_paced=False),
            to_attr="prefetched_dated_courseruns",
        )
        # Topics are serialized per course along with their parent topics, whose
        # sort key is CoursesTopic.Meta.ordering == ["parent__name", "name"] -
        # hence select_related down to the grandparent.
        topics_prefetch = Prefetch(
            "page__topics",
            queryset=CoursesTopic.objects.select_related("parent", "parent__parent"),
        )
        queryset = queryset.prefetch_related(
            "departments",
            "in_programs",
            course_runs_prefetch,
            dated_runs_prefetch,
            topics_prefetch,
            # CoursePageSerializer.get_instructors walks this for every course.
            "page__linked_instructors__linked_instructor_page",
            # Serialized by CourseSerializer.possible_variant_sets. Unfiltered,
            # unlike the v2 CourseViewSet's: this view has no org/contract
            # params to narrow it by, and ETL consumers expect every variant.
            "possible_variant_sets",
        )
        # Only a boolean is ever read from this (CourseSerializer.
        # get_certificate_available), so Exists() beats an aggregate - no
        # GROUP BY on the main query or on the paginator's COUNT. all_objects
        # keeps this view's ETL semantics, which include source runs.
        queryset = queryset.annotate(
            has_verified_courserun=verified_courserun_exists(CourseRun.all_objects),
            has_live_certificate_page=live_certificate_page_exists(),
        )
        # One queryset for both prefetches: the financial assistance URL is
        # picked by walking a course's programs, so a program this view filters
        # out of "programs" must not be able to supply the URL either.
        program_queryset = Program.objects.filter(
            live=True,
            page__live=True,
        ).only("id", "readable_id", "title", "display_mode", "program_type")
        queryset = queryset.prefetch(
            PrefetchOption(
                "financial_assistance_form_url", program_queryset=program_queryset
            ),
            PrefetchOption("programs", queryset=program_queryset),
        )

        return queryset.order_by("title").distinct()
