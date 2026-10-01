"""Tests for courses.forms"""

import json

import pytest
from django.forms.models import model_to_dict

from courses.constants import PROGRAM_DISPLAY_MODE_COURSE
from courses.factories import ProgramFactory
from courses.forms import ProgramAdminForm

pytestmark = pytest.mark.django_db


def test_program_admin_form_rejects_invalid_requirements():
    """The form validates the submitted tree against the submitted display mode"""
    program = ProgramFactory.create()
    required_program = ProgramFactory.create()
    data = {
        **model_to_dict(program, fields=ProgramAdminForm.Meta.fields),
        "departments": [department.id for department in program.departments.all()],
        "enrollment_modes": [mode.id for mode in program.enrollment_modes.all()],
        "display_mode": PROGRAM_DISPLAY_MODE_COURSE,
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
    }

    form = ProgramAdminForm(instance=program, data=data)

    assert form.is_valid() is False
    assert form.non_field_errors() == [
        "A program displayed as a course cannot require other programs."
    ]
