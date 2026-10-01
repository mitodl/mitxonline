"""Tests for courses.requirement_tree"""

import pytest

from courses.constants import PROGRAM_DISPLAY_MODE_COURSE
from courses.requirement_tree import validate_requirement_tree


def _course(course_id):
    return {"id": None, "data": {"node_type": "course", "course": course_id}}


def _program(program_id):
    return {
        "id": None,
        "data": {"node_type": "program", "required_program": program_id},
    }


def _all_of(title, *children):
    return {
        "id": None,
        "data": {"node_type": "operator", "operator": "all_of", "title": title},
        "children": list(children),
    }


def _min_of(title, value, *children):
    return {
        "id": None,
        "data": {
            "node_type": "operator",
            "operator": "min_number_of",
            "operator_value": value,
            "title": title,
            "elective_flag": True,
        },
        "children": list(children),
    }


@pytest.mark.parametrize(
    "tree",
    [
        # two-level: required courses and a required program, plus electives
        [
            _all_of("Required Courses", _course(1), _program(9)),
            _min_of("Elective Courses", "1", _course(2), _course(3)),
        ],
        # DEDP: a total pool and an advanced floor sharing course nodes
        [
            _all_of("Core", _course(1)),
            _min_of("Electives", "2", _course(2), _course(3), _course(4), _course(5)),
            _min_of("Advanced Electives", "1", _course(4), _course(5)),
        ],
        [_min_of("Optional", "0")],
    ],
    ids=["two_level", "dedp", "min_zero"],
)
def test_validate_requirement_tree_valid(tree):
    """Trees in the shapes programs use today have no errors"""
    assert validate_requirement_tree(tree, display_mode=None) == []


@pytest.mark.parametrize(
    ("tree", "display_mode", "message"),
    [
        ([_course(1)], None, "Top-level requirements must be groups"),
        ([_all_of("", _course(1))], None, "A top-level group has no Title."),
        (
            [_min_of("Electives", "1", _all_of("Group", _course(1)))],
            None,
            '"Group" is a group inside another group',
        ),
        ([_min_of("Electives", None, _course(1))], None, "whole number, 0 or more"),
        ([_min_of("Electives", "-1", _course(1))], None, "whole number, 0 or more"),
        (
            [_min_of("Electives", "2", _course(1))],
            None,
            "Value of 2 but only 1 item(s)",
        ),
        (
            [_all_of("Required", _program(9))],
            PROGRAM_DISPLAY_MODE_COURSE,
            "cannot require other programs",
        ),
    ],
    ids=[
        "top_level_course",
        "untitled_group",
        "nested_group",
        "value_missing",
        "value_negative",
        "value_above_child_count",
        "course_mode_program_node",
    ],
)
def test_validate_requirement_tree_invalid(tree, display_mode, message):
    """Each rule reports its own error"""
    errors = validate_requirement_tree(tree, display_mode=display_mode)

    assert len(errors) == 1
    assert message in errors[0]
