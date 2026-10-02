"""Tests for the check_program_requirements command"""

from io import StringIO

import pytest
from django.core.management import call_command

from courses.factories import (
    CourseFactory,
    ProgramFactory,
    program_with_requirements,  # noqa: F401
)

pytestmark = [pytest.mark.django_db]


@pytest.mark.parametrize(
    ("select_by", "checked"), [(None, 2), ("id", 1), ("readable_id", 1)]
)
def test_check_program_requirements_reports_tree_shape(
    program_with_requirements,  # noqa: F811
    select_by,
    checked,
):
    """A saved tree that breaks a validator rule is reported under its program"""
    nested = program_with_requirements.program
    flat = ProgramFactory.create()
    flat.add_requirement(CourseFactory.create())
    args = [] if select_by is None else ["--program", str(getattr(nested, select_by))]
    out = StringIO()

    call_command("check_program_requirements", *args, stdout=out)

    assert (
        f'Program {nested.readable_id}: A group in "Elective Courses" is inside '
        "a group" in out.getvalue()
    )
    assert f"Program {flat.readable_id}" not in out.getvalue()
    assert f"Checked {checked} program(s); 1 with problems" in out.getvalue()
