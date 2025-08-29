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
from courses.serializers.v1.programs import ProgramRequirementTreeSerializer
from courses.widgets import ProgramRequirementsInput


def program_requirements_schema():
    # here, you can create a schema dynamically
    # such as read data from database and populate choices

    courses = Course.objects.live().order_by("title")
    programs = Program.objects.live().order_by("title")

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
                                    ProgramRequirementNodeType.PROGRAM.value,
                                ],
                                "options": {
                                    "enum_titles": [
                                        ProgramRequirementNodeType.COURSE.label,
                                        ProgramRequirementNodeType.OPERATOR.label,
                                        ProgramRequirementNodeType.PROGRAM.label,
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
                            # program fields
                            "required_program": {
                                "type": "number",
                                "title": "Required Program",
                                "enum": [program.id for program in programs],
                                "options": {
                                    "dependencies": {
                                        "node_type": ProgramRequirementNodeType.PROGRAM.value
                                    },
                                    "enum_titles": [
                                        f"{program.readable_id} | {program.title}"
                                        for program in programs
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

    def clean(self):  # noqa: C901
        """
        Verifies that a Program's elective and requirement operators.
        Ensures that every operator has a Title defined.
        Ensures that elective operators have a Value defined which
        is less than or equal to the number of courses which can be
        applied to the program certificate.

        Raises:
            ValidationError: operator_value does not exist.
            ValidationError: operator_value does exist but is empty.
            ValidationError: operator_value is not equal to or less than the number of courses
                which can apply towards the program certificate.
        """

        def _validate_elective_value_presence(operator):
            """
            Verifies that a Program's elective operator contains
            a defined Value field.

            Args:
                operator (dict):
                {
                    'children': [],
                    'id': None,
                    'data': {
                        'node_type': 'operator',
                        'title': 'Only 1 of',
                        'operator': 'min_number_of',
                        'operator_value': '1',
                        'elective_flag': False
                    }
                }
            ValidationError: operator_value does not exist.
            ValidationError: operator_value does exist but is empty.
            """
            if (
                operator["data"]["operator"]
                == ProgramRequirement.Operator.MIN_NUMBER_OF.value
            ):
                # Ensure a Value exists and is defined for elective operators.
                if "operator_value" not in operator["data"]:
                    raise ValidationError(
                        '"Minimum # of" operator must have Value equal to 1 or more.'  # noqa: EM101
                    )
                if operator["data"]["operator_value"] == "":
                    raise ValidationError(
                        '"Minimum # of" operator must have Value equal to 1 or more.'  # noqa: EM101
                    )

        def _validate_operator_title(operator):
            """Ensure Title is defined for every operator.

            Args:
                operator (dict):
                    {
                        'children': [],
                        'id': None,
                        'data': {
                            'node_type': 'operator',
                            'title': 'Only 1 of',
                            'operator': 'min_number_of',
                            'operator_value': '1',
                            'elective_flag': False
                        }
                    }

            Raises:
                ValidationError: Operator Title value is empty.
            """
            if operator["data"]["title"] == "":
                raise ValidationError("Operator must have a Title.")  # noqa: EM101

        def _validate_elective_value_and_child_courses(
            elective_operator_value: int, number_of_applicable_courses_in_operator: int
        ):
            """Validate that the elective operations Value is equal to or less
                    than the total number of course certificates which count
                    towards satisfying the elective.

            Args:
                elective_operator_value (int): The Value field of the elective operator.
                number_of_applicable_courses_in_operator (int): The calculated total number of course
                    certificates which count towards satisfying the elective.

            Raises:
                ValidationError: The elective operator's Value is larger than the total number of course
                    certificates which count towards satisfying the elective.
            """
            if elective_operator_value > number_of_applicable_courses_in_operator:
                raise ValidationError(
                    '"Minimum # of" operator must have Value equal to or less than the number of elective courses which can apply towards the program certificate.'  # noqa: EM101
                )

        if "requirements" in self.cleaned_data:
            for operator in self.cleaned_data["requirements"]:
                # Ensure Title is defined for every operator.
                _validate_operator_title(operator)

                if (
                    operator["data"]["operator"]
                    == ProgramRequirement.Operator.MIN_NUMBER_OF.value
                ):
                    _validate_elective_value_presence(operator)

                    # Ensure the total number of courses that are allowed to apply towards the program
                    # certificate is equal to or less than the Value field for the elective.
                    total_child_courses = 0
                    for child in operator["children"]:
                        if child["data"]["node_type"] == "operator":
                            _validate_operator_title(child)
                            if (
                                operator["data"]["operator"]
                                == ProgramRequirement.Operator.MIN_NUMBER_OF.value
                            ):
                                _validate_elective_value_presence(child)
                                # Make sure the nested elective stipulation's value is equal to or less than the number
                                # of child courses associated with it.  We can assume that all children of the nested
                                # elective stipulation are courses and not operators.
                                _validate_elective_value_and_child_courses(
                                    int(child["data"]["operator_value"]),
                                    len(child["children"]),
                                )
                                # The value of the nested elective stipulation defines the number of courses
                                # within that nested stipulation which are allowed to apply towards a program's
                                # elective requirement.
                                total_child_courses += int(
                                    child["data"]["operator_value"]
                                )
                        else:
                            # Assume the child must be a course.
                            total_child_courses += 1

                    # Validate the main elective operator using child courses and nested stipulation values.
                    _validate_elective_value_and_child_courses(
                        int(operator["data"]["operator_value"]), total_child_courses
                    )

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
