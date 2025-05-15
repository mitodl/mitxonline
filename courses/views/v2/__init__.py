"""
Course API Views version 2
"""

from b2b.models import ContractPage
import django_filters
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.pagination import PageNumberPagination
from django.db.models import Exists, OuterRef, Subquery

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


class ProgramFilterSet(django_filters.FilterSet):
    org_id = django_filters.NumberFilter(method="filter_by_org_id")

    class Meta:
        model = Program
        fields = ["id", "live", "readable_id", "page__live", "org_id"]

    def filter_by_org_id(self, queryset, _, org_id):
        # Subquery for active contracts belonging to the org
        request = self.request
        user = getattr(request, "user", None)
        org_id = request.query_params.get("org_id") if request else None
        show_contracted = (
            user and user.is_authenticated and org_id and user.b2b_organizations.filter(id=org_id).exists()
        )

        if show_contracted:
            active_contracts = ContractPage.objects.filter(
                organization__id=org_id, active=True
            )
            # Subquery to find ProgramRequirements with courses that have runs in active contracts
            program_requirements_with_contract_runs = ProgramRequirement.objects.filter(
                node_type=ProgramRequirementNodeType.COURSE,
                course__courseruns__b2b_contract__in=Subquery(active_contracts.values("id")),
                program_id=OuterRef("pk"),
            )

            return queryset.annotate(
                has_contracted_courses=Exists(program_requirements_with_contract_runs)
            ).filter(has_contracted_courses=True)
        else:
            # If not showing contracted, filter out programs with any courses that have runs in active contracts
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

    permission_classes = []
    serializer_class = ProgramSerializer
    pagination_class = Pagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = ProgramFilterSet

    queryset = (
        Program.objects.filter().order_by("title").prefetch_related("departments")
    )

    @extend_schema(
        operation_id="programs_retrieve_v2",
        description="API view set for Programs - v2",
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(operation_id="programs_list_v2", description="List Programs - v2")
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class IdInFilter(django_filters.BaseInFilter, django_filters.NumberFilter):
    pass


class CourseFilterSet(django_filters.FilterSet):
    courserun_is_enrollable = django_filters.BooleanFilter(
        field_name="courserun_is_enrollable",
        method="filter_courserun_is_enrollable",
        label="Course Run Is Enrollable",
    )
    id = IdInFilter(field_name="id", lookup_expr="in", label="Course ID")

    def filter_queryset(self, queryset):
        request = self.request
        user = getattr(request, "user", None)
        org_id = request.query_params.get("org_id") if request else None

        if org_id:
            if (
                user
                and user.is_authenticated
                and user.b2b_organizations.filter(id=org_id).exists()
            ):
                queryset = queryset.filter(
                    courseruns__b2b_contract__organization_id=org_id,
                    courseruns__b2b_contract__active=True,
                )
            else:
                return queryset.none()
        else:
            queryset = queryset.filter(courseruns__b2b_contract__isnull=True)

        return super().filter_queryset(queryset.distinct())

    def filter_courserun_is_enrollable(self, queryset, _, value):
        if value:
            return get_enrollable_courses(queryset)
        return get_unenrollable_courses(queryset)

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
