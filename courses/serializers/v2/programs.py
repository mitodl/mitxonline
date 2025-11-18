from __future__ import annotations

import logging

from drf_spectacular.utils import extend_schema_field, extend_schema_serializer
from rest_framework import serializers

from cms.serializers import ProgramPageSerializer
from courses.models import Program, ProgramCollection, ProgramRequirementNodeType
from courses.serializers.base import (
    BaseProgramRequirementTreeSerializer,
    get_thumbnail_url,
)
from courses.serializers.utils import get_unique_topics_from_courses
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
    requirements = serializers.SerializerMethodField()
    req_tree = serializers.SerializerMethodField()
    page = serializers.SerializerMethodField()
    departments = DepartmentSerializer(many=True, read_only=True)
    topics = serializers.SerializerMethodField()
    certificate_type = serializers.SerializerMethodField()
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

    def get_courses(self, instance) -> list[int]:
        return [course[0].id for course in instance.courses if course[0].live]

    def get_collections(self, instance) -> list[int]:
        if hasattr(instance, "programcollection_set"):
            return [
                collection.id for collection in instance.programcollection_set.all()
            ]

        # Fallback to database query
        return [
            collection.id
            for collection in ProgramCollection.objects.filter(
                collection_items__program__id=instance.id
            )
        ]

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
                                "oneOf": [
                                    {"type": "integer"},
                                ]
                            },
                            "description": "List of required course IDs",
                        },
                        "electives": {
                            "type": "array",
                            "items": {
                                "oneOf": [
                                    {"type": "integer"},
                                ]
                            },
                            "description": "List of elective course IDs",
                        },
                    },
                },
                "programs": {
                    "type": "object",
                    "properties": {
                        "required": {
                            "type": "array",
                            "items": {
                                "oneOf": [
                                    {"type": "integer"},
                                ]
                            },
                            "description": "List of required program IDs",
                        },
                        "electives": {
                            "type": "array",
                            "items": {
                                "oneOf": [
                                    {"type": "integer"},
                                ]
                            },
                            "description": "List of elective program IDs",
                        },
                    },
                },
            },
        }
    )
    def _is_requirement_elective(self, requirement):
        """Check if a requirement is elective based on its flag or parent flag"""
        if requirement.elective_flag:
            return True
        try:
            parent = requirement.get_parent()
            return parent and bool(parent.elective_flag)
        except AttributeError:
            return False

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
        """Get program requirements using prefetched data when available"""
        if hasattr(instance, "all_requirements"):
            required_courses, elective_courses = (
                self._process_course_requirements_from_all(
                    instance.all_requirements.all()
                )
            )
            required_programs, elective_programs = (
                self._process_program_requirements_from_all(
                    instance.all_requirements.all()
                )
            )
        else:
            # Fallback to using model properties
            return {
                "courses": {
                    "required": [
                        {"id": course.id, "readable_id": course.readable_id}
                        for course in instance.required_courses
                    ],
                    "electives": [
                        {"id": course.id, "readable_id": course.readable_id}
                        for course in instance.elective_courses
                    ],
                },
                "programs": {
                    "required": [
                        {"id": program.id, "readable_id": program.readable_id}
                        for program in instance.required_programs
                    ],
                    "electives": [
                        {"id": program.id, "readable_id": program.readable_id}
                        for program in instance.elective_programs
                    ],
                },
            }

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

    def _process_course_requirements_from_all(self, requirements):
        """Process course requirements and return dicts with id and readable_id"""
        required_courses = []
        elective_courses = []
        for req in requirements:
            # Check node_type and course first to avoid unnecessary queries
            if req.node_type == ProgramRequirementNodeType.COURSE and req.course:
                course_data = {
                    "id": req.course.id,
                    "readable_id": req.course.readable_id,
                }
                if self._is_requirement_elective(req):
                    elective_courses.append(course_data)
                else:
                    required_courses.append(course_data)
        return required_courses, elective_courses

    def _process_program_requirements_from_all(self, requirements):
        """Process program requirements and return dicts with id and readable_id"""
        required_programs = []
        elective_programs = []
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
                if self._is_requirement_elective(req):
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

    @extend_schema_field(ProgramPageSerializer)
    def get_page(self, instance):
        if hasattr(instance, "page"):
            return ProgramPageSerializer(instance.page).data
        else:
            return {"feature_image_src": get_thumbnail_url(None)}

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
        # Check if we have prefetched all_requirements to avoid N+1 queries
        if hasattr(instance, "all_requirements"):
            courses = [
                req.course
                for req in instance.all_requirements.all()
                if req.node_type == ProgramRequirementNodeType.COURSE and req.course
            ]
            return get_unique_topics_from_courses(courses)
        else:
            # Fallback to original courses property if prefetch not available
            return get_unique_topics_from_courses(instance.courses)

    @extend_schema_field(str)
    def get_certificate_type(self, instance):
        if "MicroMasters" in instance.program_type:
            return "MicroMasters Credential"
        return "Certificate of Completion"

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

    def get_min_price(self, instance) -> int | None:
        """
        Get the min price of the product from the CMS page.
        """
        if hasattr(instance, "page") and hasattr(instance.page, "min_price"):
            return instance.page.min_price
        return None

    def get_max_price(self, instance) -> int | None:
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
            "requirements",
            "req_tree",
            "page",
            "program_type",
            "certificate_type",
            "departments",
            "live",
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
        ]


@extend_schema_serializer(component_name="V2UserProgramEnrollmentDetail")
class UserProgramEnrollmentDetailSerializer(serializers.Serializer):
    """
    Serializer for user program enrollments with associated course enrollments.

    This aggregates a program, its course enrollments for the user, and any
    program certificate that has been earned.
    """

    program = ProgramSerializer()
    certificate = serializers.SerializerMethodField(read_only=True)

    def get_fields(self):
        """Import serializers here to avoid circular imports."""
        fields = super().get_fields()
        fields["enrollments"] = CourseRunEnrollmentSerializer(many=True)
        return fields

    @extend_schema_field(
        {
            "allOf": [{"$ref": "#/components/schemas/V2ProgramCertificate"}],
            "nullable": True,
        }
    )
    def get_certificate(self, instance):
        """
        Resolve a certificate for this enrollment if it exists.
        """
        from courses.serializers.v2.certificates import ProgramCertificateSerializer

        certificate = instance.get("certificate")
        return ProgramCertificateSerializer(certificate).data if certificate else None
