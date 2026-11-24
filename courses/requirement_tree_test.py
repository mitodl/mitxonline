"""Tests for courses.requirement_tree"""

import pytest

from courses.constants import PROGRAM_DISPLAY_MODE_COURSE
from courses.factories import CourseFactory, ProgramFactory
from courses.requirement_tree import (
    RequirementResult,
    explain_requirement_tree,
    is_requirement_tree_satisfied,
    programs_requiring,
    validate_requirement_tree,
)


def _course(course_id):
    return {"id": None, "data": {"node_type": "course", "course": course_id}}


def _program(program_id):
    return {
        "id": None,
        "data": {"node_type": "program", "required_program": program_id},
    }


def _all_of(title, *children, **data):
    return {
        "id": None,
        "data": {"node_type": "operator", "operator": "all_of", "title": title, **data},
        "children": list(children),
    }


def _min_of(title, value, *children, **data):
    return {
        "id": None,
        "data": {
            "node_type": "operator",
            "operator": "min_number_of",
            "operator_value": value,
            "title": title,
            "elective_flag": True,
            **data,
        },
        "children": list(children),
    }


def _track(title, *children):
    return {
        "id": None,
        "data": {"node_type": "track", "title": title},
        "children": list(children),
    }


def _valid_track(title="A Track"):
    return _track(title, _all_of("Required", _course(7), _course(8)))


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
        # tracks: core, then one of two tracks, one with its own elective group
        [
            _all_of("Core", _course(1)),
            _min_of(
                "Tracks",
                "1",
                _valid_track("General Track"),
                _track(
                    "Methods Track",
                    _all_of("Required", _course(2)),
                    _min_of("Electives", "1", _course(3), _course(4)),
                ),
            ),
        ],
    ],
    ids=["two_level", "dedp", "min_zero", "tracks"],
)
def test_validate_requirement_tree_valid(tree):
    """Trees in the shapes programs use have no errors"""
    assert validate_requirement_tree(tree, display_mode=None) == []


@pytest.mark.parametrize(
    ("tree", "display_mode", "message"),
    [
        ([_course(1)], None, "Top-level requirements must be groups"),
        ([_all_of("", _course(1))], None, "A top-level group has no Title."),
        (
            [
                {
                    "id": None,
                    "data": {"node_type": "operator", "title": "Group"},
                    "children": [_course(1)],
                }
            ],
            None,
            '"Group" needs an operator',
        ),
        (
            [_min_of("Electives", "1", _all_of("Group", _course(1)))],
            None,
            '"Group" is inside a group',
        ),
        (
            [_all_of("Required", {**_course(1), "children": [_course(2)]})],
            None,
            "Courses and programs cannot contain other requirements.",
        ),
        ([_min_of("Electives", None, _course(1))], None, "whole number, 0 or more"),
        ([_min_of("Electives", "-1", _course(1))], None, "whole number, 0 or more"),
        (
            [_min_of("Electives", "2", _course(1))],
            None,
            "Value of 2 but only 1 item(s)",
        ),
        (
            [_min_of("Electives", "2", _course(1), _course(1), _course(2))],
            None,
            '"Electives" lists a course more than once.',
        ),
        (
            [_all_of("Required", _program(9))],
            PROGRAM_DISPLAY_MODE_COURSE,
            "cannot require other programs",
        ),
        (
            [_valid_track()],
            None,
            'Track "A Track" must be inside a top-level "Minimum # of" group.',
        ),
        (
            [_all_of("Tracks", _valid_track(), elective_flag=True)],
            None,
            '"Tracks" holds tracks, so it must be a "Minimum # of" group.',
        ),
        (
            [_min_of("Tracks", "2", _valid_track("A"), _valid_track("B"))],
            None,
            '"Tracks" holds tracks, so its "Minimum # of" Value must be 1',
        ),
        (
            [_min_of("Tracks", "1", _valid_track(), _course(1))],
            None,
            '"Tracks" holds tracks, so every item in it must be a track.',
        ),
        (
            [_min_of("Tracks", "1", _valid_track(), elective_flag=False)],
            None,
            '"Tracks" holds tracks, so it must be an elective group.',
        ),
        (
            [
                _min_of("Tracks", "1", _valid_track("A")),
                _min_of("More Tracks", "1", _valid_track("B")),
            ],
            None,
            "only one group of tracks",
        ),
        (
            [_min_of("Tracks", "1", _track("Idle Track", _all_of("Required")))],
            None,
            'Track "Idle Track" requires nothing',
        ),
        (
            [_min_of("Tracks", "1", _track("Flat Track", _course(1)))],
            None,
            "A track can only hold groups, not individual courses or programs.",
        ),
        (
            [_min_of("Tracks", "1", _track("", _all_of("Required", _course(1))))],
            None,
            'A track in "Tracks" has no Title.',
        ),
        (
            [_min_of("Tracks", "1", _valid_track())],
            PROGRAM_DISPLAY_MODE_COURSE,
            "A program displayed as a course cannot have tracks.",
        ),
    ],
    ids=[
        "top_level_course",
        "untitled_group",
        "no_operator",
        "nested_group",
        "course_with_children",
        "value_missing",
        "value_negative",
        "value_above_child_count",
        "duplicate_in_group",
        "course_mode_program_node",
        "track_at_top_level",
        "container_not_min_number_of",
        "container_value_not_one",
        "container_mixed_items",
        "container_not_elective",
        "two_containers",
        "track_requires_nothing",
        "track_with_course",
        "untitled_track",
        "course_mode_tracks",
    ],
)
def test_validate_requirement_tree_invalid(tree, display_mode, message):
    """Each rule reports its own error"""
    errors = validate_requirement_tree(tree, display_mode=display_mode)

    assert len(errors) == 1
    assert message in errors[0]


@pytest.mark.parametrize(
    ("required_program", "message"),
    [
        (1, "A program cannot require itself."),
        (
            2,
            '"Parent" already requires this program, so this program cannot '
            "require it.",
        ),
    ],
    ids=["itself", "program_requiring_it"],
)
def test_validate_requirement_tree_rejects_program_cycles(required_program, message):
    """A program cannot require itself or a program that already requires it"""
    errors = validate_requirement_tree(
        [_all_of("Required", _program(required_program))],
        display_mode=None,
        program_id=1,
        programs_requiring_this={2: "Parent"},
    )

    assert errors == [message]


@pytest.mark.django_db
def test_programs_requiring_follows_required_programs():
    """Programs requiring the program directly or through another are returned"""
    program = ProgramFactory.create()
    parent = ProgramFactory.create()
    parent.add_program_requirement(program)
    grandparent = ProgramFactory.create()
    grandparent.add_program_requirement(parent)
    ProgramFactory.create().add_program_requirement(ProgramFactory.create())

    assert programs_requiring(program.id) == {
        parent.id: parent.title,
        grandparent.id: grandparent.title,
    }


def _add_group(parent, title, operator, value=None, node_type="operator"):
    return parent.add_child(
        node_type=node_type,
        operator=operator,
        operator_value=value,
        title=title,
    )


@pytest.fixture
def tracks_program():
    """
    A program needing course 1, at least 1 of courses 2 and 3, and one of two
    tracks: course 4, or courses 5 and 6.
    """
    program = ProgramFactory.create()
    courses = CourseFactory.create_batch(6)
    root = program.requirements_root
    core = _add_group(root, "Core", "all_of")
    core.add_child(node_type="course", course=courses[0])
    electives = _add_group(root, "Electives", "min_number_of", "1")
    for course in courses[1:3]:
        electives.add_child(node_type="course", course=course)
    tracks = _add_group(root, "Tracks", "min_number_of", "1")
    first = _add_group(tracks, "First", None, node_type="track")
    _add_group(first, "Required", "all_of").add_child(
        node_type="course", course=courses[3]
    )
    second = _add_group(tracks, "Second", None, node_type="track")
    second_required = _add_group(second, "Required", "all_of")
    for course in courses[4:]:
        second_required.add_child(node_type="course", course=course)
    return program, courses


def _leaf_from(passed_course_ids):
    def explain_leaf(node):
        return RequirementResult(
            label=f"course {node.course_id}",
            satisfied=node.course_id in passed_course_ids,
            detail="" if node.course_id in passed_course_ids else "not passed",
        )

    return explain_leaf


@pytest.mark.django_db
@pytest.mark.parametrize(
    "passed",
    [
        [],
        [0],
        [0, 1],
        [0, 1, 3],
        [0, 2, 4],
        [0, 2, 4, 5],
        [1, 2, 3, 4, 5],
    ],
)
def test_explain_requirement_tree_agrees_with_is_satisfied(tracks_program, passed):
    """explain_requirement_tree's overall result matches is_requirement_tree_satisfied"""
    program, courses = tracks_program
    passed_ids = {courses[index].id for index in passed}

    result = explain_requirement_tree(program, explain_leaf=_leaf_from(passed_ids))

    assert result.satisfied is is_requirement_tree_satisfied(
        program,
        course_satisfied=passed_ids.__contains__,
        program_satisfied=lambda _: False,
    )


@pytest.mark.django_db
def test_explain_requirement_tree_reports_every_unmet_item(tracks_program):
    """Every group is evaluated, and each reports how many of its items are met"""
    program, courses = tracks_program
    passed_ids = {courses[0].id, courses[4].id}

    result = explain_requirement_tree(program, explain_leaf=_leaf_from(passed_ids))

    assert result.format_lines() == [
        f"✗ {program.title} ({program.readable_id}): all 3 needed, 1 met",
        '  ✓ "Core": all 1 needed, 1 met',
        f"    ✓ course {courses[0].id}",
        '  ✗ "Electives": at least 1 of 2 needed, 0 met',
        f"    ✗ course {courses[1].id}: not passed",
        f"    ✗ course {courses[2].id}: not passed",
        '  ✗ "Tracks": at least 1 of 2 needed, 0 met',
        '    ✗ Track "First": all 1 needed, 0 met',
        '      ✗ "Required": all 1 needed, 0 met',
        f"        ✗ course {courses[3].id}: not passed",
        '    ✗ Track "Second": all 1 needed, 0 met',
        '      ✗ "Required": all 2 needed, 1 met',
        f"        ✓ course {courses[4].id}",
        f"        ✗ course {courses[5].id}: not passed",
    ]
    assert [leaf.label for leaf in result.unmet_leaves()] == [
        f"course {courses[index].id}" for index in (1, 2, 3, 5)
    ]


@pytest.mark.django_db
def test_explain_requirement_tree_without_requirements():
    """A program with no requirements root has nothing to explain"""
    program = ProgramFactory.create()
    program.all_requirements.all().delete()

    assert explain_requirement_tree(program, explain_leaf=_leaf_from(set())) is None
