"""
Course API Views version 2
"""

import django_filters
from django.db.models import Prefetch, Q
from django_filters.rest_framework import DjangoFilterBackend
from mitol.common.utils import now_in_utc
from rest_framework import viewsets
from rest_framework.pagination import PageNumberPagination

from courses.models import (
    Course,
    CourseRun,
    Department,
    Program,
)
from courses.serializers.v2.courses import (
    CourseWithCourseRunsSerializer,
)
from courses.serializers.v2.departments import (
    DepartmentWithCoursesAndProgramsSerializer,
)
from courses.serializers.v2.programs import ProgramSerializer


class Pagination(PageNumberPagination):
    """Paginator class for infinite loading"""

    page_size = 12
    page_size_query_param = "page_size"
    max_page_size = 100
    ordering = "-created_on"


class ProgramViewSet(viewsets.ReadOnlyModelViewSet):
    """API viewset for Programs"""

    permission_classes = []

    serializer_class = ProgramSerializer
    pagination_class = Pagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["id", "live", "readable_id", "page__live"]
    queryset = (
        Program.objects.filter().order_by("title").prefetch_related("departments")
    )


class IdInFilter(django_filters.BaseInFilter, django_filters.NumberFilter):
    pass


class CourseFilterSet(django_filters.FilterSet):
    courserun_is_enrollable = django_filters.BooleanFilter(
        field_name="courserun_is_enrollable",
        method="filter_courserun_is_enrollable",
        label="Course Run Is Enrollable",
    )
    id = IdInFilter(field_name="id", lookup_expr="in", label="Course ID")

    def filter_courserun_is_enrollable(self, queryset, _, value):
        """
        courserun_is_enrollable filter to narrow down runs that are open for
        enrollments
        """
        now = now_in_utc()

        if value is True:
            enrollable_runs = CourseRun.objects.filter(
                Q(live=True)
                & Q(start_date__isnull=False)
                & Q(enrollment_start__lt=now)
                & (Q(enrollment_end=None) | Q(enrollment_end__gt=now))
            )
            return (
                queryset.prefetch_related(
                    Prefetch("courseruns", queryset=enrollable_runs),
                )
                .prefetch_related("courseruns__course")
                .filter(courseruns__id__in=enrollable_runs.values_list("id", flat=True))
                .distinct()
            )

        else:
            unenrollable_runs = CourseRun.objects.filter(
                Q(live=False) | Q(start_date__isnull=True) | Q(enrollment_end__lte=now)
            )
            return (
                queryset.prefetch_related(
                    Prefetch("courseruns", queryset=unenrollable_runs)
                )
                .prefetch_related("courseruns__course")
                .filter(
                    courseruns__id__in=unenrollable_runs.values_list("id", flat=True)
                )
                .distinct()
            )

    class Meta:
        model = Course
        fields = ["id", "live", "readable_id", "page__live", "courserun_is_enrollable"]


class CourseViewSet(viewsets.ReadOnlyModelViewSet):
    """API view set for Courses"""

    pagination_class = Pagination
    permission_classes = []
    filter_backends = [DjangoFilterBackend]
    serializer_class = CourseWithCourseRunsSerializer
    filterset_class = CourseFilterSet

    def get_queryset(self):
        return (
            Course.objects.filter()
            .select_related("page")
            .prefetch_related("departments")
            .all()
            .order_by("title")
        )

    def get_serializer_context(self):
        added_context = {}
        if self.request.query_params.get("readable_id", None):
            added_context["all_runs"] = True
        if self.request.query_params.get("include_approved_financial_aid", None):
            added_context["include_approved_financial_aid"] = True

        return {**super().get_serializer_context(), **added_context}


class DepartmentViewSet(viewsets.ReadOnlyModelViewSet):
    """API view set for Departments"""

    serializer_class = DepartmentWithCoursesAndProgramsSerializer
    pagination_class = Pagination
    permission_classes = []

    def get_queryset(self):
        return Department.objects.all().order_by("name")
