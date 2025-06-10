"""
Course API Views version 2
"""

import django_filters
from django.db.models import Count, Exists, OuterRef
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from courses.models import (
    Course,
    CoursesTopic,
    Department,
    Program,
    ProgramRequirement,
    ProgramRequirementNodeType,
)
from courses.serializers.v2.courses import (
    CourseTopicSerializer,
    CourseWithCourseRunsSerializer,
)
from courses.serializers.v2.departments import (
    DepartmentWithCoursesAndProgramsSerializer,
)
from courses.serializers.v2.programs import ProgramSerializer
from courses.utils import get_enrollable_courses, get_unenrollable_courses


class Pagination(PageNumberPagination):
    """Paginator class for infinite loading"""

    page_size = 12
    page_size_query_param = "page_size"
    max_page_size = 100
    ordering = "-created_on"


def user_has_org_access(user, org_id):
    return (
        user
        and user.is_authenticated
        and org_id
        and user.b2b_organizations.filter(id=org_id).exists()
    )


class ProgramFilterSet(django_filters.FilterSet):
    org_id = django_filters.NumberFilter(method="filter_by_org_id")

    class Meta:
        model = Program
        fields = ["id", "live", "readable_id", "page__live", "org_id"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def qs(self):
        """If the request isn't explicitly filtering on org_id, exclude contracted courses."""

        if "org_id" not in getattr(self.request, "GET", {}):
            program_requirements_with_contract_runs = ProgramRequirement.objects.filter(
                node_type=ProgramRequirementNodeType.COURSE,
                course__courseruns__b2b_contract__isnull=False,
                program_id=OuterRef("pk"),
            )
            return (
                super()
                .qs.annotate(
                    has_contracted_courses=Exists(
                        program_requirements_with_contract_runs
                    )
                )
                .filter(has_contracted_courses=False)
            )

        return super().qs

    def filter_by_org_id(self, queryset, _, org_id):
        if self.request and user_has_org_access(self.request.user, org_id):
            program_requirements_with_contract_runs = ProgramRequirement.objects.filter(
                node_type=ProgramRequirementNodeType.COURSE,
                course__courseruns__b2b_contract__organization_id=org_id,
                course__courseruns__b2b_contract__active=True,
                program_id=OuterRef("pk"),
            )
            return queryset.annotate(
                has_contracted_courses=Exists(program_requirements_with_contract_runs)
            ).filter(has_contracted_courses=True)
        else:
            program_requirements_with_contract_runs = ProgramRequirement.objects.filter(
                node_type=ProgramRequirementNodeType.COURSE,
                course__courseruns__b2b_contract__isnull=False,
                program_id=OuterRef("pk"),
            )
            return queryset.annotate(
                has_contracted_courses=Exists(program_requirements_with_contract_runs)
            ).filter(has_contracted_courses=False)


class ProgramViewSet(viewsets.ReadOnlyModelViewSet):
    """API viewset for Programs"""

    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class = ProgramSerializer
    pagination_class = Pagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = ProgramFilterSet

    def get_queryset(self):
        """Get the queryset"""
        return Program.objects.order_by("title").prefetch_related("departments")

    @extend_schema(
        operation_id="programs_retrieve_v2",
        description="API view set for Programs - v2",
    )
    def retrieve(self, request, *args, **kwargs):
        """Retrieve a specific program."""
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(operation_id="programs_list_v2", description="List Programs - v2")
    def list(self, request, *args, **kwargs):
        """List the available programs."""
        return super().list(request, *args, **kwargs)


class IdInFilter(django_filters.BaseInFilter, django_filters.NumberFilter):
    pass


class CourseFilterSet(django_filters.FilterSet):
    courserun_is_enrollable = django_filters.BooleanFilter(
        method="filter_courserun_is_enrollable",
        label="Course Run Is Enrollable",
        field_name="courserun_is_enrollable",
    )
    id = IdInFilter(field_name="id", lookup_expr="in", label="Course ID")
    org_id = django_filters.NumberFilter(
        method="filter_org_id",
        label="Only show courses beloning to this B2B/UAI organization",
        field_name="org_id",
    )
    include_approved_financial_aid = django_filters.BooleanFilter(
        method="filter_include_approved_financial_aid",
        label="Include approved financial assistance information",
        field_name="include_approved_financial_aid",
    )

    class Meta:
        model = Course
        fields = [
            "id",
            "live",
            "readable_id",
            "page__live",
            "courserun_is_enrollable",
            "org_id",
            "include_approved_financial_aid",
        ]

    def filter_org_id(self, queryset, _, value):
        """
        Filter just courses that have course runs that have B2B courses in them
        that match the specified org_id, if we're in that org.
        """
        user = self.request.user

        if user_has_org_access(user, value):
            return queryset.filter(
                courseruns__b2b_contract__organization_id=value,
                courseruns__b2b_contract__active=True,
            )
        return Course.objects.none()

    def filter_include_approved_financial_aid(self, queryset, *_):
        """
        No-op filter for include_approved_financial_aid.

        This is a serializer context flag, but the filter needs to know about
        the field so the API spec is generated correctly.
        """
        return queryset

    def filter_courserun_is_enrollable(self, queryset, _, value):
        return (
            get_enrollable_courses(queryset)
            if value
            else get_unenrollable_courses(queryset)
        )


class CourseViewSet(viewsets.ReadOnlyModelViewSet):
    """API view set for Courses"""

    pagination_class = Pagination
    permission_classes = []
    filter_backends = [DjangoFilterBackend]
    serializer_class = CourseWithCourseRunsSerializer
    filterset_class = CourseFilterSet

    def get_queryset(self):
        """Get the queryset for the viewset."""

        return (
            Course.objects.select_related("page")
            .prefetch_related("departments")
            .annotate(count_b2b_courseruns=Count("courseruns__b2b_contract__id"))
            .annotate(count_courseruns=Count("courseruns"))
            .order_by("title")
            .distinct()
        )

    def get_serializer_context(self):
        added_context = {}
        qp = self.request.query_params
        if qp.get("readable_id"):
            added_context["all_runs"] = True
        if qp.get("include_approved_financial_aid"):
            added_context["include_approved_financial_aid"] = True
        if qp.get("org_id"):
            added_context["org_id"] = qp.get("org_id")
        return {**super().get_serializer_context(), **added_context}

    @extend_schema(
        operation_id="api_v2_courses_retrieve",
        description="Retrieve a specific course - API v2",
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        operation_id="api_v2_courses_list", description="List all courses - API v2"
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class DepartmentViewSet(viewsets.ReadOnlyModelViewSet):
    """API view set for Departments"""

    serializer_class = DepartmentWithCoursesAndProgramsSerializer
    permission_classes = []

    def get_queryset(self):
        return Department.objects.all().order_by("name")

    @extend_schema(
        operation_id="departments_retrieve_v2",
        description="Get department details - v2",
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        operation_id="departments_list_v2", description="List departments - v2"
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class CourseTopicViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Readonly viewset for parent course topics.
    """

    permission_classes = []
    serializer_class = CourseTopicSerializer

    def get_queryset(self):
        """
        Returns parent topics with course count > 0.
        """
        return CoursesTopic.parent_topics_with_courses()
