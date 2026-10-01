"""Evaluation of a program's requirement tree."""

from collections import defaultdict
from collections.abc import Callable

from mitol.common.utils.queryset import is_prefetched

from courses.models import Program, ProgramRequirement


def _requirement_nodes(program: Program) -> list[ProgramRequirement]:
    """Return every requirement node of the program, root included."""
    nodes = program.all_requirements.all()
    if not is_prefetched(program, "all_requirements"):
        nodes = nodes.select_related("required_program")
    return list(nodes)


def is_requirement_tree_satisfied(
    program: Program,
    *,
    course_satisfied: Callable[[int], bool],
    program_satisfied: Callable[[Program], bool],
) -> bool:
    """
    Evaluate the program's requirement tree against two leaf predicates.

    Children are grouped by materialized path from a single read of the
    program's nodes (the prefetched ``all_requirements`` when present), so
    evaluation costs no queries per node beyond what the predicates make.

    Args:
        program: the program whose tree is evaluated.
        course_satisfied: called with the course id of each course node.
        program_satisfied: called with the required program of each program node.

    Returns:
        bool: False when the program has no requirements root.
    """
    root = None
    children = defaultdict(list)
    for node in _requirement_nodes(program):
        if node.is_root:
            root = node
        else:
            children[node.path[: -ProgramRequirement.steplen]].append(node)

    if root is None:
        return False

    def _satisfied(node):
        if node.is_root or node.is_all_of_operator:
            return all(_satisfied(child) for child in children[node.path])
        if node.is_min_number_of_operator:
            passed = sum(1 for child in children[node.path] if _satisfied(child))
            return passed >= int(node.operator_value)
        if node.is_course:
            return course_satisfied(node.course_id)
        if node.is_program:
            return program_satisfied(node.required_program)
        return False

    return _satisfied(root)
