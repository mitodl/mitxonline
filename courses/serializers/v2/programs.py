from __future__ import annotations

import logging
from decimal import Decimal  # noqa: TC003

from drf_spectacular.utils import extend_schema_field, extend_schema_serializer
from rest_framework import serializers

from cms.models import CoursePage
from cms.serializers import ProgramPageSerializer
from courses.models import (
    Program,
    ProgramCertificate,
    ProgramCollection,
    ProgramRequirement,
    ProgramRequirementNodeType,
)
from courses.serializers.base import BaseProgramRequirementTreeSerializer
from courses.serializers.v1.base import (
    BaseProgramSerializer,
    EnrollmentModeSerializer,
    ProductRelatedField,
)
from courses.serializers.v1.departments import DepartmentSerializer
from courses.serializers.v2.courses import CourseRunEnrollmentSerializer
from main.serializers import StrictFieldsSerializer

logger = logging.getLogger(__name__)


@extend_schema_serializer(component_name="V2ProgramRequirementData")
class ProgramRequirementDataSerializer(StrictFieldsSerializer):
    """Serializer for ProgramRequirement data"""

    node_type = serializers.ChoiceField(
        choices=(
            ProgramRequirementNodeType.COURSE,
            ProgramRequirementNodeType.PROGRAM,
            ProgramRequirementNodeType.OPERATOR,
        )
    )
    course = serializers.IntegerField(source="course_id", allow_null=True, default=None)
    program = serializers.IntegerField(
        source="program_id", allow_null=True, default=None
    )
    required_program = serializers.IntegerField(
        source="required_program_id", allow_null=True, default=None
    )
    title = serializers.CharField(allow_null=True, default=None)
    operator = serializers.CharField(allow_null=True, default=None)
    operator_value = serializers.CharField(allow_null=True, default=None)
    elective_flag = serializers.BooleanField(allow_null=True, default=False)


@extend_schema_serializer(component_name="V2ProgramRequirement")
class ProgramRequirementSerializer(StrictFieldsSerializer):
    """Serializer for a ProgramRequirement"""

    id = serializers.IntegerField(required=False, allow_null=True, default=None)
    data = ProgramRequirementDataSerializer()

    def get_fields(self):
        """Override because 'children' is a recursive structure"""
        fields = super().get_fields()
        fields["children"] = ProgramRequirementSerializer(many=True, default=[])
        return fields


@extend_schema_serializer(component_name="V2ProgramCollection")
class ProgramCollectionSerializer(StrictFieldsSerializer):
    """Serializer for ProgramCollection"""

    id = serializers.IntegerField(read_only=True)
    title = serializers.CharField()
    description = serializers.CharField()
    programs = serializers.SerializerMethodField()
    created_on = serializers.DateTimeField(read_only=True)
    updated_on = serializers.DateTimeField(read_only=True)

    class Meta:
        model = ProgramCollection
        fields = [
            "id",
            "title",
            "description",
            "programs",
            "created_on",
            "updated_on",
        ]

    @extend_schema_field(
        field={
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "title": {"type": "string"},
                    "order": {"type": "integer"},
                },
            },
        }
    )
    def get_programs(self, instance) -> list[dict[str, int | str]]:
        """
        Returns programs in the collection ordered by their order field
        """
        return [
            {
                "id": item.program.id,
                "title": item.program.title,
                "order": item.sort_order,
            }
            for item in instance.ordered_collection_items
        ]


class ProgramRequirementTreeSerializer(BaseProgramRequirementTreeSerializer):
    child = ProgramRequirementSerializer()

    @property
    def data(self):
        """Return children of root node directly, or empty array if no children"""
        # BaseProgramRequirementTreeSerializer overrides the data property
        # to bypass to_implementation, so we do also.
        full_data = super().data
        return full_data[0].get("children", []) if full_data else []


@extend_schema_serializer(
    component_name="V2ProgramSerializer",
)
class ProgramSerializer(serializers.ModelSerializer):
    """Program Model Serializer v2"""

    courses = serializers.SerializerMethodField()
    collections = serializers.SerializerMethodField()
    programs = serializers.SerializerMethodField()
    requirements = serializers.SerializerMethodField()
    req_tree = serializers.SerializerMethodField()
    page = serializers.SerializerMethodField()
    departments = DepartmentSerializer(many=True, read_only=True)
    topics = serializers.SerializerMethodField()
    certificate_type = serializers.SerializerMethodField()
    certificate_available = serializers.SerializerMethodField()
    required_prerequisites = serializers.SerializerMethodField()
    duration = serializers.SerializerMethodField()
    min_weeks = serializers.SerializerMethodField()
    max_weeks = serializers.SerializerMethodField()
    time_commitment = serializers.SerializerMethodField()
    min_weekly_hours = serializers.SerializerMethodField()
    max_weekly_hours = serializers.SerializerMethodField()
    min_price = serializers.SerializerMethodField()
    max_price = serializers.SerializerMethodField()
    start_date = serializers.SerializerMethodField()
    enrollment_modes = EnrollmentModeSerializer(many=True, read_only=True)

    @extend_schema_field(BaseProgramSerializer(many=True, allow_null=True))
    def get_programs(self, instance):
        """Include parent programs for this program when requested.

        This mirrors the behavior of the CourseSerializer.get_programs method,
        but uses the ProgramRequirement.required_program reverse relation
        ("required_by") instead of Course.in_programs.
        """
        if not self.context.get("include_programs", False):
            return None

        programs_qs = instance.required_by

        if self.context.get("org_id"):
            programs_qs = programs_qs.filter(
                program__contract_memberships__contract__organization__pk=self.context.get(
                    "org_id"
                )
            )
        elif self.context.get("contract_id"):
            programs_qs = programs_qs.filter(
                program__contract_memberships__contract__pk=self.context.get(
                    "contract_id"
                )
            )
        else:
            programs_qs = programs_qs.filter(program__b2b_only=False)

        programs_qs = programs_qs.filter(program__live=True, program__page__live=True)

        programs = [req.program for req in programs_qs.select_related("program").all()]

        return BaseProgramSerializer(programs, many=True).data

    def get_courses(self, instance) -> list[int]:
        return [course[0].id for course in instance.courses if course[0].live]

    def get_collections(self, instance) -> list[int]:
        return _get_program_collection_ids(instance)

    @extend_schema_field(
        {
            "type": "object",
            "properties": {
                "courses": {
                    "type": "object",
                    "properties": {
                        "required": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "integer"},
                                    "readable_id": {"type": "string"},
                                },
                            },
                            "description": "List of required courses with id and readable_id",
                        },
                        "electives": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "integer"},
                                    "readable_id": {"type": "string"},
                                },
                            },
                            "description": "List of elective courses with id and readable_id",
                        },
                    },
                },
                "programs": {
                    "type": "object",
                    "properties": {
                        "required": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "integer"},
                                    "readable_id": {"type": "string"},
                                },
                            },
                            "description": "List of required programs with id and readable_id",
                        },
                        "electives": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "integer"},
                                    "readable_id": {"type": "string"},
                                },
                            },
                            "description": "List of elective programs with id and readable_id",
                        },
                    },
                },
            },
        }
    )
    def get_requirements(self, instance):
        """Get program requirements using prefetched data when available."""
        all_requirements = _get_all_program_requirements(instance)
        required_courses, elective_courses = self._process_course_requirements_from_all(
            instance, all_requirements
        )
        required_programs, elective_programs = (
            self._process_program_requirements_from_all(all_requirements)
        )

        return {
            "courses": {
                "required": required_courses,
                "electives": elective_courses,
            },
            "programs": {
                "required": required_programs,
                "electives": elective_programs,
            },
        }

    def _process_course_requirements_from_all(self, instance, requirements):
        """Process course requirements and return dicts with id and readable_id."""
        requirements_data = instance.get_courses_with_requirements_data(requirements)

        return (
            [
                {"id": course.id, "readable_id": course.readable_id}
                for course in requirements_data["required_courses"]
            ],
            [
                {"id": course.id, "readable_id": course.readable_id}
                for course in requirements_data["elective_courses"]
            ],
        )

    def _process_program_requirements_from_all(self, requirements):
        """Process program requirements and return dicts with id and readable_id."""
        required_programs = []
        elective_programs = []
        elective_operator_paths = _get_elective_operator_paths(requirements)

        for req in requirements:
            # Check node_type and required_program first to avoid unnecessary queries
            if (
                req.node_type == ProgramRequirementNodeType.PROGRAM
                and req.required_program
            ):
                program_data = {
                    "id": req.required_program.id,
                    "readable_id": req.required_program.readable_id,
                }
                if _is_requirement_under_elective_operator(
                    req, elective_operator_paths
                ):
                    elective_programs.append(program_data)
                else:
                    required_programs.append(program_data)
        return required_programs, elective_programs

    def get_required_prerequisites(self, instance) -> bool:
        """
        Check if the prerequisites field is populated in the program page CMS.
        """
        return bool(
            hasattr(instance, "page")
            and hasattr(instance.page, "prerequisites")
            and instance.page.prerequisites != ""
        )

    def get_duration(self, instance) -> str | None:
        """
        Get the length/duration field from the program page CMS.
        """
        if hasattr(instance, "page") and hasattr(instance.page, "length"):
            return instance.page.length

        return None

    def get_time_commitment(self, instance) -> str | None:
        """
        Get the effort/time_commitment field from the program page CMS.
        """
        if hasattr(instance, "page") and hasattr(instance.page, "effort"):
            return instance.page.effort

        return None

    @extend_schema_field(ProgramRequirementTreeSerializer)
    def get_req_tree(self, instance):
        req_root = instance.get_requirements_root()

        if req_root is None:
            return []

        return ProgramRequirementTreeSerializer(instance=req_root).data

    @extend_schema_field(ProgramPageSerializer(allow_null=True))
    def get_page(self, instance):
        if hasattr(instance, "page") and instance.page is not None:
            return ProgramPageSerializer(instance.page).data
        return None

    @extend_schema_field(
        {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                    },
                },
            },
        }
    )
    def get_topics(self, instance):
        """Get unique topics from courses using prefetched data to avoid N+1 queries"""
        courses = _get_program_courses(instance)
        if not courses:
            return []

        return _get_unique_topics_from_course_ids([course.id for course in courses])

    @extend_schema_field(str)
    def get_certificate_type(self, instance):
        if "MicroMasters" in instance.program_type:
            return "MicroMasters Credential"
        return "Certificate of Completion"

    @extend_schema_field(bool)
    def get_certificate_available(self, instance) -> bool:
        return any(mode.requires_payment for mode in instance.enrollment_modes.all())

    def get_min_weekly_hours(self, instance) -> str | None:
        """
        Get the min weekly hours of the course from the course page CMS.
        """
        if hasattr(instance, "page") and hasattr(instance.page, "min_weekly_hours"):
            return instance.page.min_weekly_hours

        return None

    def get_max_weekly_hours(self, instance) -> str | None:
        """
        Get the max weekly hours of the course from the course page CMS.
        """
        if hasattr(instance, "page") and hasattr(instance.page, "max_weekly_hours"):
            return instance.page.max_weekly_hours

        return None

    def get_min_weeks(self, instance) -> int | None:
        """
        Get the min weeks of the program from the CMS page.
        """
        if hasattr(instance, "page") and hasattr(instance.page, "min_weeks"):
            return instance.page.min_weeks

        return None

    def get_max_weeks(self, instance) -> int | None:
        """
        Get the max weeks of the program from the CMS page.
        """
        if hasattr(instance, "page") and hasattr(instance.page, "max_weeks"):
            return instance.page.max_weeks

        return None

    def get_min_price(self, instance) -> Decimal | None:
        """
        Get the min price of the product from the CMS page.
        """
        if hasattr(instance, "page") and hasattr(instance.page, "min_price"):
            return instance.page.min_price
        return None

    def get_max_price(self, instance) -> Decimal | None:
        """
        Get the max price of the product from the CMS page.
        """
        if hasattr(instance, "page") and hasattr(instance.page, "max_price"):
            return instance.page.max_price
        return None

    def get_start_date(self, instance) -> str | None:
        """
        Get the start date of the program by finding the first available run.
        """
        # Use next_starting_run property to avoid repeated queries
        next_run = instance.next_starting_run

        if next_run and next_run.start_date:
            return next_run.start_date
        return instance.start_date

    class Meta:
        model = Program
        fields = [
            "title",
            "readable_id",
            "id",
            "courses",
            "collections",
            "programs",
            "requirements",
            "req_tree",
            "page",
            "program_type",
            "certificate_type",
            "certificate_available",
            "departments",
            "live",
            "display_mode",
            "topics",
            "availability",
            "start_date",
            "end_date",
            "enrollment_start",
            "enrollment_end",
            "required_prerequisites",
            "duration",
            "min_weeks",
            "max_weeks",
            "min_price",
            "max_price",
            "time_commitment",
            "min_weekly_hours",
            "max_weekly_hours",
            "enrollment_modes",
        ]


@extend_schema_serializer(component_name="V2ProgramDetailSerializer")
class ProgramDetailSerializer(ProgramSerializer):
    """Extended Program serializer that includes products. Used by the programs API."""

    products = serializers.SerializerMethodField()

    class Meta(ProgramSerializer.Meta):
        fields = [*ProgramSerializer.Meta.fields, "products"]

    @extend_schema_field(ProductRelatedField(many=True, read_only=True))
    def get_products(self, instance):
        # Use prefetched products if available, otherwise fallback to related manager
        products = getattr(instance, "prefetched_products", None)
        if products is not None:
            return ProductRelatedField(many=True, read_only=True).to_representation(
                products
            )
        return ProductRelatedField(many=True, read_only=True).to_representation(
            instance.products.all()
        )


class ProgramCertificateSerializer(serializers.ModelSerializer):
    """ProgramCertificate model serializer"""

    class Meta:
        model = ProgramCertificate
        fields = ["uuid", "link"]


@extend_schema_serializer(component_name="V2UserProgramEnrollmentDetail")
class UserProgramEnrollmentDetailSerializer(serializers.Serializer):
    """
    Serializer for user program enrollments with associated course enrollments.

    This aggregates a program, its course enrollments for the user, and any
    program certificate that has been earned.
    """

    program = ProgramSerializer()
    enrollments = CourseRunEnrollmentSerializer(many=True)
    certificate = serializers.SerializerMethodField(read_only=True)

    @extend_schema_field(ProgramCertificateSerializer(allow_null=True))
    def get_certificate(self, instance):
        """
        Resolve a certificate for this enrollment if it exists.
        """
        certificate = instance.get("certificate")
        return ProgramCertificateSerializer(certificate).data if certificate else None


def _get_program_collection_ids(instance: Program) -> list[int]:
    """Return collection IDs using prefetched memberships when available."""
    memberships = getattr(instance, "prefetched_collection_memberships", None)
    if memberships is not None:
        return [membership.collection_id for membership in memberships]

    prefetched_memberships = getattr(instance, "_prefetched_objects_cache", {}).get(
        "collection_memberships"
    )
    if prefetched_memberships is not None:
        return [membership.collection_id for membership in prefetched_memberships]

    return list(
        ProgramCollection.objects.filter(collection_items__program_id=instance.id)
        .values_list("id", flat=True)
        .order_by("collection_items__sort_order", "id")
    )


def _get_all_program_requirements(instance: Program) -> list[ProgramRequirement]:
    """Return all requirements using prefetched data when available."""

    cached_requirements = getattr(instance, "_prefetched_objects_cache", {}).get(
        "all_requirements"
    )
    if cached_requirements is not None:
        return list(cached_requirements)

    return list(
        ProgramRequirement.objects.select_related("course", "required_program")
        .filter(program_id=instance.id)
        .order_by("path")
    )


def _get_elective_operator_paths(requirements: list[ProgramRequirement]) -> set[str]:
    """Return the set of operator paths that mark descendants as elective."""
    return {
        requirement.path
        for requirement in requirements
        if requirement.node_type == ProgramRequirementNodeType.OPERATOR
        and requirement.elective_flag
    }


def _is_requirement_under_elective_operator(
    requirement: ProgramRequirement, elective_operator_paths: set[str]
) -> bool:
    """Return True if a requirement is elective by itself or by ancestry."""
    return bool(requirement.elective_flag) or any(
        requirement.path.startswith(operator_path)
        for operator_path in elective_operator_paths
    )


def _get_program_courses(instance: Program) -> list:
    """Return live course objects for a program using normalized requirement data."""
    return [
        course
        for course, _ in instance.get_courses_with_requirements_data()["courses"]
        if course and course.live
    ]


def _get_unique_topics_from_course_ids(course_ids: list[int]) -> list[dict[str, str]]:
    """Return unique topic payloads for the given course IDs with a single query."""
    if not course_ids:
        return []

    topic_names = (
        CoursePage.objects.filter(course_id__in=course_ids, topics__isnull=False)
        .values_list("topics__name", flat=True)
        .distinct()
        .order_by("topics__name")
    )

    return [{"name": topic_name} for topic_name in topic_names]
