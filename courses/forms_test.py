"""Tests for courses.forms"""

import json

import pytest
from django.forms.models import model_to_dict

from courses.constants import PROGRAM_DISPLAY_MODE_COURSE
from courses.factories import ProgramFactory
from courses.forms import ProgramAdminForm

pytestmark = pytest.mark.django_db


def _form_data(program, required_program, **overrides):
    """Form data for the program with one required group holding required_program"""
    return {
        **model_to_dict(program, fields=ProgramAdminForm.Meta.fields),
        "departments": [department.id for department in program.departments.all()],
        "enrollment_modes": [mode.id for mode in program.enrollment_modes.all()],
        "requirements": json.dumps(
            [
                {
                    "data": {
                        "node_type": "operator",
                        "title": "Required Courses",
                        "operator": "all_of",
                    },
                    "children": [
                        {
                            "data": {
                                "node_type": "program",
                                "required_program": required_program.id,
                            }
                        }
                    ],
                }
            ]
        ),
        **overrides,
    }


def test_program_admin_form_rejects_invalid_requirements():
    """The form validates the submitted tree against the submitted display mode"""
    program = ProgramFactory.create()
    data = _form_data(
        program, ProgramFactory.create(), display_mode=PROGRAM_DISPLAY_MODE_COURSE
    )

    form = ProgramAdminForm(instance=program, data=data)

    assert form.is_valid() is False
    assert form.non_field_errors() == [
        "A program displayed as a course cannot require other programs."
    ]


def test_program_admin_form_rejects_requirement_cycles():
    """The form rejects requiring a program that already requires this one"""
    program = ProgramFactory.create()
    parent = ProgramFactory.create()
    parent.add_program_requirement(program)

    form = ProgramAdminForm(instance=program, data=_form_data(program, parent))

    assert form.is_valid() is False
    assert form.non_field_errors() == [
        f'"{parent.title}" already requires this program, so this program cannot '
        "require it."
    ]
