"""Validation and evaluation of a program's requirement tree."""

from collections import defaultdict
from collections.abc import Callable

from mitol.common.utils.queryset import is_prefetched

from courses.constants import PROGRAM_DISPLAY_MODE_COURSE
from courses.models import Program, ProgramRequirement, ProgramRequirementNodeType


def _group_name(title, parent_title):
    if title:
        return f'"{title}"'
    if parent_title:
        return f'A group in "{parent_title}"'
    return "A top-level group"


def _min_number_of_errors(name, data, children, *, top_level) -> list[str]:
    errors = []
    if not top_level:
        errors.append(
            f'{name} is a "Minimum # of" group inside another group; '
            '"Minimum # of" groups can only be at the top level.'
        )
    try:
        value = int(str(data.get("operator_value")).strip())
    except ValueError:
        value = None
    if value is None or value < 0:
        errors.append(
            f'{name} needs a "Minimum # of" Value that is a whole number, 0 or more.'
        )
    # The evaluator counts each satisfied child once, so a larger value can
    # never be met.
    elif value > len(children):
        errors.append(
            f'{name} has a "Minimum # of" Value of {value} but only '
            f"{len(children)} item(s) to choose from."
        )
    return errors


def validate_requirement_tree(
    tree: list[dict], *, display_mode: str | None
) -> list[str]:
    """
    Check a requirement tree against the rules every saved tree must follow.

    Args:
        tree: the root's children, each ``{"id", "data": {...}, "children": [...]}``
            as ProgramAdminForm submits them and ``dump_bulk`` produces them.
            Leaf nodes may omit ``children``.
        display_mode: the program's ``display_mode``.

    Returns:
        list[str]: one message per problem found; empty when the tree is valid.
    """
    errors = []

    def _visit(node, *, top_level, parent_title):
        data = node.get("data", {})
        node_type = data.get("node_type")

        if (
            node_type == ProgramRequirementNodeType.PROGRAM
            and display_mode == PROGRAM_DISPLAY_MODE_COURSE
        ):
            errors.append(
                "A program displayed as a course cannot require other programs."
            )
        if node_type != ProgramRequirementNodeType.OPERATOR:
            return

        title = (data.get("title") or "").strip()
        name = _group_name(title, parent_title)
        children = node.get("children") or []
        if not title:
            errors.append(f"{name} has no Title.")
        if data.get("operator") == ProgramRequirement.Operator.MIN_NUMBER_OF:
            errors.extend(
                _min_number_of_errors(name, data, children, top_level=top_level)
            )
        for child in children:
            _visit(child, top_level=False, parent_title=title or parent_title)

    for node in tree:
        if node.get("data", {}).get("node_type") != ProgramRequirementNodeType.OPERATOR:
            errors.append(
                "Top-level requirements must be groups, not individual courses or programs."
            )
        _visit(node, top_level=True, parent_title=None)

    return errors


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
