from django import forms
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.forms import ModelForm, ValidationError
from django.forms.fields import JSONField
from webpack_loader import utils as webpack_loader_utils

from courses.models import (
    Course,
    CourseRun,
    Program,
    ProgramRequirement,
    ProgramRequirementNodeType,
)
from courses.requirement_tree import programs_requiring, validate_requirement_tree
from courses.serializers.v1.programs import ProgramRequirementTreeSerializer
from courses.widgets import ProgramRequirementsInput

#: Courseware ID suffix of the runs offered by the admin "enroll in runs" page
ADMIN_ENROLL_RUN_SUFFIX = "0T2026"


def program_requirements_catalog():
    """
    Build the course/program catalog the requirements builder searches over.

    The requirements-admin.js widget renders its own "requirement groups" UI
    client-side; this just hands it the raw data it needs to populate course
    and program pickers, the node types it writes, and the operator choices
    for a group's "all of" / "choose N of" toggle.
    """

    courses = Course.objects.live().order_by("title")
    programs = Program.objects.live().order_by("title")

    return {
        "nodeTypes": {
            "course": ProgramRequirementNodeType.COURSE.value,
            "operator": ProgramRequirementNodeType.OPERATOR.value,
            "program": ProgramRequirementNodeType.PROGRAM.value,
            "track": ProgramRequirementNodeType.TRACK.value,
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
            program_id = self.instance.pk
            errors = validate_requirement_tree(
                cleaned_data["requirements"],
                display_mode=cleaned_data.get("display_mode"),
                program_id=program_id,
                programs_requiring_this=(
                    programs_requiring(program_id) if program_id else {}
                ),
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


class AdminEnrollUserInRunsForm(forms.Form):
    """
    Admin form for enrolling one user in any of the course runs whose
    courseware_id ends with ADMIN_ENROLL_RUN_SUFFIX.
    """

    user = forms.CharField(
        help_text="Email, username, or ID of the user to enroll",
        widget=forms.TextInput(attrs={"size": 60}),
    )
    runs = forms.ModelMultipleChoiceField(
        queryset=CourseRun.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        help_text=f"Course runs ending in {ADMIN_ENROLL_RUN_SUFFIX}",
    )

    def __init__(self, *args, **kwargs):
        """Populate the run choices at form creation so new runs show up."""
        super().__init__(*args, **kwargs)
        self.fields["runs"].queryset = (
            CourseRun.objects.filter(courseware_id__endswith=ADMIN_ENROLL_RUN_SUFFIX)
            .select_related("course")
            .order_by("courseware_id")
        )
        self.fields["runs"].label_from_instance = lambda run: (
            f"{run.courseware_id} — {run.title}"
        )

    def clean_user(self):
        """Resolve the entered email, username, or ID to a single User."""
        value = self.cleaned_data["user"].strip()
        query = Q(email__iexact=value) | Q(username=value)
        if value.isdigit():
            query |= Q(pk=int(value))
        users = list(get_user_model().objects.filter(query)[:2])
        if not users:
            msg = f"No user found matching '{value}'"
            raise ValidationError(msg)
        if len(users) > 1:
            msg = f"More than one user matches '{value}'; use the user ID instead"
            raise ValidationError(msg)
        return users[0]
