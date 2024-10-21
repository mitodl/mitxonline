import logging

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

    def get_courses(self, instance):
        return [course[0].id for course in instance.courses if course[0].live]

    def get_requirements(self, instance):
        return {
            "required": [course.id for course in instance.required_courses],
            "electives": [course.id for course in instance.elective_courses],
        }

    def get_required_prerequisites(self, instance):
        """
        Check if the prerequisites field is populated in the program page CMS.
        """
        return bool(
            hasattr(instance, "page")
            and hasattr(instance.page, "prerequisites")
            and instance.page.prerequisites != ""
        )

    def get_req_tree(self, instance):
        req_root = instance.get_requirements_root()

        if req_root is None:
            return []

        return ProgramRequirementTreeSerializer(instance=req_root).data

    def get_page(self, instance):
        if hasattr(instance, "page"):
            return ProgramPageSerializer(instance.page).data
        else:
            return {"feature_image_src": get_thumbnail_url(None)}

    def get_topics(self, instance):
        """List all topics in all courses in the program"""
        topics = set(  # noqa: C401
            topic.name
            for course in instance.courses
            if hasattr(course[0], "page") and course[0].page is not None
            for topic in course[0].page.topics.all()
        )
        return [{"name": topic} for topic in sorted(topics)]

    def get_certificate_type(self, instance):
        if "MicroMasters" in instance.program_type:
            return "MicroMasters Credential"
        return "Certificate of Completion"

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
        ]


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
