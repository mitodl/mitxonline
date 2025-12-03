from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from courses.models import Course, ProgramRequirement


@dataclasses.dataclass(kw_only=True)
class CourseRequirements:
    all: list[Course]
    required: list[Course]
    electives: list[Course]


@dataclasses.dataclass(kw_only=True)
class ProgramRequirements:
    all: list[Course]
    required: list[Course]
    electives: list[Course]


@dataclasses.dataclass(kw_only=True)
class Requirements:
    required_title: str
    elective_title: str

    courses: CourseRequirements
    programs: ProgramRequirements

    minimum_elective_requirement: None | int = None

    @classmethod
    def from_nodes(cls, nodes: list[ProgramRequirement]) -> Requirements:
        """Create requirements from a set of nodes"""
        required_title = "Required Courses"
        required_courses = []
        required_programs = []
        elective_title = "Elective Courses"
        elective_courses = []
        elective_programs = []
        minimum_elective_requirement = None
        all_courses = []
        all_programs = []

        is_elective = False

        # the tree is a flat list ordered by path, so we walk it while tracking
        # whether we're currently in electives or not
        for node in nodes:
            if node.is_operator:
                is_elective = node.elective_flag
                if is_elective:
                    elective_title = node.title or elective_title
                    if (
                        node.is_min_number_of_operator
                        and minimum_elective_requirement is None
                        and node.operator_value
                    ):
                        minimum_elective_requirement = int(node.operator_value)
                else:
                    required_title = node.title or required_title
            elif node.is_course:
                course = node.course
                all_courses.append(course)
                if is_elective:
                    elective_courses.append(course)
                else:
                    required_courses.append(course)
            elif node.is_program:
                program = node.program
                all_programs.append(program)
                if is_elective:
                    elective_programs.append(program)
                else:
                    required_programs.append(program)

        return cls(
            required_title=required_title,
            elective_title=elective_title,
            courses=CourseRequirements(
                all=all_courses,
                required=required_courses,
                electives=elective_courses,
            ),
            programs=ProgramRequirements(
                all=all_programs,
                required=required_programs,
                electives=elective_programs,
            ),
            minimum_elective_requirement=minimum_elective_requirement,
        )
