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
from courses.serializers import ProgramRequirementTreeSerializer
from courses.widgets import ProgramRequirementsInput


def program_requirements_schema():
    # here, you can create a schema dynamically
    # such as read data from database and populate choices

    courses = Course.objects.live().order_by("title")

    return {
        "title": "Requirements",
        "type": "array",
        "items": {
            "$ref": "#/$defs/node",
            "title": "Section",
            "headerTemplate": "{{ self.data.title }}",
            "options": {
                "disable_collapse": False,
                "collapsed": True,
            },
            "properties": {
                "data": {
                    "type": "object",
                    "properties": {
                        "node_type": {
                            "type": "string",
                            "default": ProgramRequirementNodeType.OPERATOR.value,
                            "options": {
                                "hidden": True,
                            },
                        }
                    },
                },
                "children": {
                    "type": "array",
                    "title": "Requirements",
                    "items": {
                        "title": "Requirement",
                        "$ref": "#/$defs/node",
                        "properties": {
                            "children": {
                                "type": "array",
                                "title": "Courses",
                                "format": "table",
                                "options": {
                                    "dependencies": {
                                        "data.node_type": ProgramRequirementNodeType.OPERATOR.value,
                                    }
                                },
                                "items": {
                                    "$ref": "#/$defs/node",
                                    "title": "Course",
                                    "properties": {
                                        "data": {
                                            "title": "Courses",
                                            "properties": {
                                                "node_type": {
                                                    "type": "string",
                                                    "default": ProgramRequirementNodeType.COURSE.value,
                                                    "options": {
                                                        "hidden": True,
                                                    },
                                                }
                                            },
                                        },
                                    },
                                },
                            }
                        },
                    },
                },
            },
        },
        "$defs": {
            "node": {
                "type": "object",
                "properties": {
                    "id": {
                        "type": ["number", "null"],
                        "default": None,
                        "options": {
                            "hidden": True,
                        },
                    },
                    "data": {
                        "type": "object",
                        "title": "Details",
                        "propertyOrder": 1,
                        "properties": {
                            "node_type": {
                                "type": "string",
                                "title": "Type",
                                "enum": [
                                    ProgramRequirementNodeType.COURSE.value,
                                    ProgramRequirementNodeType.OPERATOR.value,
                                ],
                                "options": {
                                    "enum_titles": [
                                        ProgramRequirementNodeType.COURSE.label,
                                        ProgramRequirementNodeType.OPERATOR.label,
                                    ],
                                },
                            },
                            "title": {
                                "type": "string",
                                "title": "Title",
                                "options": {
                                    "dependencies": {
                                        "node_type": ProgramRequirementNodeType.OPERATOR.value,
                                    }
                                },
                            },
                            "operator": {
                                "type": "string",
                                "title": "Operation",
                                "enum": ProgramRequirement.Operator.values,
                                "options": {
                                    "dependencies": {
                                        "node_type": ProgramRequirementNodeType.OPERATOR.value,
                                    },
                                    "enum_titles": ProgramRequirement.Operator.labels,
                                },
                            },
                            "operator_value": {
                                "type": "string",
                                "format": "number",
                                "title": "Value",
                                "default": 1,
                                "options": {
                                    "dependencies": {
                                        "node_type": ProgramRequirementNodeType.OPERATOR.value,
                                        "operator": ProgramRequirement.Operator.MIN_NUMBER_OF.value,
                                    },
                                },
                            },
                            "elective_flag": {
                                "type": "boolean",
                                "title": "Contains Electives",
                                "default": False,
                                "options": {
                                    "dependencies": {
                                        "node_type": ProgramRequirementNodeType.OPERATOR.value,
                                    },
                                },
                            },
                            # course fields
                            "course": {
                                "type": "number",
                                "title": "Course",
                                "enum": [course.id for course in courses],
                                "options": {
                                    "dependencies": {
                                        "node_type": ProgramRequirementNodeType.COURSE.value
                                    },
                                    "enum_titles": [
                                        f"{course.readable_id} | {course.title}"
                                        for course in courses
                                    ],
                                },
                            },
                        },
                    },
                },
            },
        },
    }


class ProgramAdminForm(ModelForm):
    """Custom form for handling requirements data"""

    requirements = JSONField(
        widget=ProgramRequirementsInput(schema=program_requirements_schema)
    )

    def __init__(self, *args, **kwargs):
        initial = kwargs.pop("initial", {})
        instance = kwargs.get("instance", None)

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
        if "requirements" in self.cleaned_data:
            for operator in self.cleaned_data["requirements"]:
                if (
                    operator["data"]["operator"]
                    == ProgramRequirement.Operator.MIN_NUMBER_OF.value
                ):
                    if "operator_value" not in operator["data"]:
                        raise ValidationError(
                            '"Minimum # of" operator must have Value equal to 1 or more.'
                        )
                    if operator["data"]["operator_value"] == "":
                        raise ValidationError(
                            '"Minimum # of" operator must have Value equal to 1 or more.'
                        )
                    if len(operator["children"]) < int(
                        operator["data"]["operator_value"]
                    ):
                        raise ValidationError(
                            '"Minimum # of" operator must have Value equal to or less than the number of elective courses in the section.'
                        )
                if operator["data"]["title"] == "":
                    raise ValidationError("Section must have a Title.")

    def save(self, commit=True):
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
            "live",
            "requirements",
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
