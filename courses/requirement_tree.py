"""Validation and evaluation of a program's requirement tree."""

from collections import defaultdict
from collections.abc import Callable, Mapping

from mitol.common.utils.queryset import is_prefetched

from courses.constants import PROGRAM_DISPLAY_MODE_COURSE
from courses.models import Program, ProgramRequirement, ProgramRequirementNodeType


def _group_name(title, parent_title):
    if title:
        return f'"{title}"'
    if parent_title:
        return f'A group in "{parent_title}"'
    return "A top-level group"


# The shapes Learn renders, as the child node types each node type may hold.
# Its product page shows each top-level group's direct courses and programs and
# drops a nested group
# (https://github.com/mitodl/mit-learn/blob/b6d0e97e0d619ff30eb3479e9395574ce2254dfc/frontends/main/src/app-pages/ProductPages/util.ts#L34-L78),
# and its dashboard progress skips one
# (https://github.com/mitodl/mit-learn/blob/b6d0e97e0d619ff30eb3479e9395574ce2254dfc/frontends/main/src/app-pages/DashboardPage/CoursewareDisplay/model/dashboardViewModel.ts#L222-L232).
# The evaluator handles any nesting, so this widens when Learn does.
_ALLOWED_CHILDREN = {
    ProgramRequirementNodeType.PROGRAM_ROOT: {ProgramRequirementNodeType.OPERATOR},
    ProgramRequirementNodeType.OPERATOR: {
        ProgramRequirementNodeType.COURSE,
        ProgramRequirementNodeType.PROGRAM,
    },
}


def _placement_error(parent_type, title, parent_title) -> str:
    """The message for a node that _ALLOWED_CHILDREN does not allow under its parent."""
    if parent_type == ProgramRequirementNodeType.PROGRAM_ROOT:
        return (
            "Top-level requirements must be groups, not individual courses or programs."
        )
    return (
        f"{_group_name(title, parent_title)} is inside a group; groups can "
        "contain only courses and programs."
    )


def _operator_value_errors(name, data, children) -> list[str]:
    try:
        value = int(str(data.get("operator_value")).strip())
    except ValueError:
        value = None
    if value is None or value < 0:
        return [
            f'{name} needs a "Minimum # of" Value that is a whole number, 0 or more.'
        ]
    # The evaluator counts each satisfied child once, so a larger value can
    # never be met.
    if value > len(children):
        return [
            f'{name} has a "Minimum # of" Value of {value} but only '
            f"{len(children)} item(s) to choose from."
        ]
    return []


def _program_node_errors(
    required_program, *, display_mode, program_id, programs_requiring_this
) -> list[str]:
    errors = []
    if display_mode == PROGRAM_DISPLAY_MODE_COURSE:
        errors.append("A program displayed as a course cannot require other programs.")
    if program_id is not None and required_program == program_id:
        errors.append("A program cannot require itself.")
    elif required_program in programs_requiring_this:
        errors.append(
            f'"{programs_requiring_this[required_program]}" already requires this '
            "program, so this program cannot require it."
        )
    return errors


def validate_requirement_tree(
    tree: list[dict],
    *,
    display_mode: str | None,
    program_id: int | None = None,
    programs_requiring_this: Mapping[int, str] | None = None,
) -> list[str]:
    """
    Check a requirement tree against the rules every saved tree must follow.

    Each node must be a child type that ``_ALLOWED_CHILDREN`` allows under its
    parent. The other rules hold at any depth: every group has a title and an
    operator; a "Minimum # of" group's value is a whole number no larger than
    its number of children; a program displayed as a course requires no
    programs; and a program requires neither itself nor a program that already
    requires it, which would make evaluating either tree recurse forever.

    Args:
        tree: the root's children, each ``{"id", "data": {...}, "children": [...]}``
            as ProgramAdminForm submits them and ``dump_bulk`` produces them.
            Leaf nodes may omit ``children``.
        display_mode: the program's ``display_mode``.
        program_id: the id of the program whose tree this is; None for a
            program not yet saved.
        programs_requiring_this: title by id of every program that already
            requires this one, as ``programs_requiring`` returns them.

    Returns:
        list[str]: one message per problem found; empty when the tree is valid.
    """
    errors = []
    programs_requiring_this = programs_requiring_this or {}

    def _visit(node, *, parent_type, parent_title):
        data = node.get("data", {})
        node_type = data.get("node_type")
        title = (data.get("title") or "").strip()

        if node_type not in _ALLOWED_CHILDREN[parent_type]:
            errors.append(_placement_error(parent_type, title, parent_title))
        if node_type == ProgramRequirementNodeType.PROGRAM:
            errors.extend(
                _program_node_errors(
                    data.get("required_program"),
                    display_mode=display_mode,
                    program_id=program_id,
                    programs_requiring_this=programs_requiring_this,
                )
            )
        if node_type != ProgramRequirementNodeType.OPERATOR:
            return

        name = _group_name(title, parent_title)
        children = node.get("children") or []
        if not title:
            errors.append(f"{name} has no Title.")
        if data.get("operator") not in ProgramRequirement.Operator.values:
            errors.append(f'{name} needs an operator: "All of" or "Minimum # of".')
        if data.get("operator") == ProgramRequirement.Operator.MIN_NUMBER_OF:
            errors.extend(_operator_value_errors(name, data, children))
        for child in children:
            _visit(child, parent_type=node_type, parent_title=title or parent_title)

    for node in tree:
        _visit(
            node, parent_type=ProgramRequirementNodeType.PROGRAM_ROOT, parent_title=None
        )

    return errors


def programs_requiring(program_id: int) -> dict[int, str]:
    """
    Return the title, by id, of every program whose saved tree requires the
    given program, directly or through other required programs.

    Costs one query per level of required programs, plus one for the titles.
    """
    found = set()
    frontier = {program_id}
    while frontier:
        frontier = (
            set(
                ProgramRequirement.objects.filter(
                    node_type=ProgramRequirementNodeType.PROGRAM,
                    required_program_id__in=frontier,
                ).values_list("program_id", flat=True)
            )
            - found
        )
        found |= frontier
    return dict(Program.objects.filter(id__in=found).values_list("id", "title"))


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
