from django.db import transaction
from django.forms import ModelForm, ValidationError
from django.forms.fields import JSONField
from webpack_loader import utils as webpack_loader_utils

from courses.models import (
    Course,
    Program,
    ProgramRequirement,
    ProgramRequirementNodeType,
)
from courses.requirement_tree import validate_requirement_tree
from courses.serializers.v1.programs import ProgramRequirementTreeSerializer
from courses.widgets import ProgramRequirementsInput


def program_requirements_catalog():
    """
    Build the course/program catalog the requirements builder searches over.

    The requirements-admin.js widget renders its own "requirement groups" UI
    client-side; this just hands it the raw data it needs to populate course
    and program pickers, plus the operator choices for a group's "all of" /
    "choose N of" toggle.
    """

    courses = Course.objects.live().order_by("title")
    programs = Program.objects.live().order_by("title")

    return {
        "nodeTypes": {
            "course": ProgramRequirementNodeType.COURSE.value,
            "operator": ProgramRequirementNodeType.OPERATOR.value,
            "program": ProgramRequirementNodeType.PROGRAM.value,
        },
        "operators": [
            {"value": value, "label": label}
            for value, label in ProgramRequirement.Operator.choices
        ],
        "operatorValues": {
            "allOf": ProgramRequirement.Operator.ALL_OF.value,
            "minNumberOf": ProgramRequirement.Operator.MIN_NUMBER_OF.value,
        },
        "courses": [
            {"id": course.id, "code": course.readable_id, "title": course.title}
            for course in courses
        ],
        "programs": [
            {"id": program.id, "code": program.readable_id, "title": program.title}
            for program in programs
        ],
    }


class ProgramAdminForm(ModelForm):
    """Custom form for handling requirements data"""

    requirements = JSONField(
        widget=ProgramRequirementsInput(catalog=program_requirements_catalog)
    )

    def __init__(self, *args, **kwargs):
        initial = kwargs.pop("initial", {})
        instance = kwargs.get("instance")

        if instance is not None and instance.requirements_root is not None:
            initial["requirements"] = self._serialize_requirements(
                instance.requirements_root
            )

        if not initial.get("requirements", None):
            initial["requirements"] = [
                {
                    "data": {
                        "node_type": ProgramRequirementNodeType.OPERATOR.value,
                        "title": "Required Courses",
                        "operator_value": None,
                        "operator": ProgramRequirement.Operator.ALL_OF.value,
                        "elective_flag": False,
                    },
                    "children": [],
                },
                {
                    "data": {
                        "node_type": ProgramRequirementNodeType.OPERATOR.value,
                        "title": "Elective Courses",
                        "operator": ProgramRequirement.Operator.MIN_NUMBER_OF.value,
                        "operator_value": 1,
                        "elective_flag": True,
                    },
                    "children": [],
                },
            ]

        super().__init__(*args, initial=initial, **kwargs)

    def _serialize_requirements(self, root):
        data = ProgramRequirement.dump_bulk(parent=root, keep_ids=True)[0].get(
            "children", []
        )

        def _serialize(node):
            return {
                **node,
                "children": [_serialize(child) for child in node.get("children", [])],
            }

        return [_serialize(node) for node in data]

    def clean(self):
        """Reject a requirements tree that breaks validate_requirement_tree's rules."""
        cleaned_data = super().clean()
        if "requirements" in cleaned_data:
            errors = validate_requirement_tree(
                cleaned_data["requirements"],
                display_mode=cleaned_data.get("display_mode"),
            )
            if errors:
                raise ValidationError(errors)
        return cleaned_data

    def save(self, commit=True):  # noqa: FBT002
        """Save requirements"""
        program = super().save(commit=commit)
        transaction.on_commit(self._save_requirements)
        return program

    def _save_requirements(self):
        """
        Save related program requirements.
        """
        with transaction.atomic():
            program = self.instance
            root = program.get_requirements_root(for_update=True)

            if root is None:
                root = ProgramRequirement.add_root(
                    program=program,
                    node_type=ProgramRequirementNodeType.PROGRAM_ROOT.value,
                )

            serializer = ProgramRequirementTreeSerializer(
                root,
                context={
                    "program": program,
                },
                data=self.cleaned_data["requirements"],
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()

    class Meta:
        model = Program
        fields = [
            "title",
            "readable_id",
            "program_type",
            "departments",
            "live",
            "requirements",
            "availability",
            "start_date",
            "end_date",
            "enrollment_start",
            "enrollment_end",
            "b2b_only",
            "display_mode",
            "enrollment_modes",
            "certificates_disabled",
        ]

    class Media:
        css = {
            "all": [
                chunk["url"]
                for chunk in webpack_loader_utils.get_files("requirementsAdmin", "css")
            ],
        }
        js = [
            chunk["url"]
            for chunk in webpack_loader_utils.get_files("requirementsAdmin", "js")
        ]
