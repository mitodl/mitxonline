import logging

from drf_spectacular.utils import extend_schema_field, extend_schema_serializer
from rest_framework import serializers

from cms.serializers import ProgramPageSerializer
from courses.models import Program, ProgramRequirementNodeType
from courses.serializers.base import (
    BaseProgramRequirementTreeSerializer,
    get_thumbnail_url,
)
from courses.serializers.v1.departments import DepartmentSerializer
from main.serializers import StrictFieldsSerializer

logger = logging.getLogger(__name__)


@extend_schema_serializer(component_name="V2ProgramRequirementData")
class ProgramRequirementDataSerializer(StrictFieldsSerializer):
    """Serializer for ProgramRequirement data"""

    node_type = serializers.ChoiceField(
        choices=(
            ProgramRequirementNodeType.OPERATOR,
            ProgramRequirementNodeType.COURSE,
        )
    )
    course = serializers.CharField(source="course_id", allow_null=True, default=None)
    program = serializers.CharField(source="program_id", required=False)
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


class ProgramRequirementTreeSerializer(BaseProgramRequirementTreeSerializer):
    child = ProgramRequirementSerializer()


@extend_schema_serializer(
    component_name="V2ProgramSerializer",
)
class ProgramSerializer(serializers.ModelSerializer):
    """Program Model Serializer v2"""

    courses = serializers.SerializerMethodField()
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

    @extend_schema_field(list)
    def get_courses(self, instance):
        return [course[0].id for course in instance.courses if course[0].live]

    @extend_schema_field(
        {
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
        }
    )
    def get_requirements(self, instance):
        return {
            "required": [course.id for course in instance.required_courses],
            "electives": [course.id for course in instance.elective_courses],
        }

    @extend_schema_field(dict)
    def get_required_prerequisites(self, instance):
        """
        Check if the prerequisites field is populated in the program page CMS.
        """
        return bool(
            hasattr(instance, "page")
            and hasattr(instance.page, "prerequisites")
            and instance.page.prerequisites != ""
        )

    @extend_schema_field(int)
    def get_duration(self, instance):
        """
        Get the length/duration field from the program page CMS.
        """
        if hasattr(instance, "page") and hasattr(instance.page, "length"):
            return instance.page.length

        return None

    @extend_schema_field(str)
    def get_time_commitment(self, instance):
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

    @extend_schema_field(list)
    def get_topics(self, instance):
        """List all topics in all courses in the program"""
        topics = set(  # noqa: C401
            topic.name
            for course in instance.courses
            if hasattr(course[0], "page") and course[0].page is not None
            for topic in course[0].page.topics.all()
        )
        return [{"name": topic} for topic in sorted(topics)]

    @extend_schema_field(str)
    def get_certificate_type(self, instance):
        if "MicroMasters" in instance.program_type:
            return "MicroMasters Credential"
        return "Certificate of Completion"

    @extend_schema_field(int)
    def get_min_weekly_hours(self, instance):
        """
        Get the min weekly hours of the course from the course page CMS.
        """
        if hasattr(instance, "page") and hasattr(instance.page, "min_weekly_hours"):
            return instance.page.min_weekly_hours

        return None

    @extend_schema_field(int)
    def get_max_weekly_hours(self, instance):
        """
        Get the max weekly hours of the course from the course page CMS.
        """
        if hasattr(instance, "page") and hasattr(instance.page, "max_weekly_hours"):
            return instance.page.max_weekly_hours

        return None

    @extend_schema_field(int)
    def get_min_weeks(self, instance):
        """
        Get the min weeks of the program from the CMS page.
        """
        if hasattr(instance, "page") and hasattr(instance.page, "min_weeks"):
            return instance.page.min_weeks

        return None

    @extend_schema_field(int)
    def get_max_weeks(self, instance):
        """
        Get the max weeks of the program from the CMS page.
        """
        if hasattr(instance, "page") and hasattr(instance.page, "max_weeks"):
            return instance.page.max_weeks

        return None

    class Meta:
        model = Program
        fields = [
            "title",
            "readable_id",
            "id",
            "courses",
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
            "time_commitment",
            "min_weekly_hours",
            "max_weekly_hours",
        ]
