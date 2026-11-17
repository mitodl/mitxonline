"""Validation and evaluation of a program's requirement tree."""

from collections import Counter, defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

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
# Tracks are the one nesting allowed; Learn is to show each track as a flat
# list of groups (mitodl/hq#13656). The evaluator handles any nesting, so this
# widens when Learn does.
_ALLOWED_CHILDREN = {
    ProgramRequirementNodeType.PROGRAM_ROOT: {ProgramRequirementNodeType.OPERATOR},
    ProgramRequirementNodeType.OPERATOR: {
        ProgramRequirementNodeType.COURSE,
        ProgramRequirementNodeType.PROGRAM,
        ProgramRequirementNodeType.TRACK,
    },
    ProgramRequirementNodeType.TRACK: {ProgramRequirementNodeType.OPERATOR},
    ProgramRequirementNodeType.COURSE: set(),
    ProgramRequirementNodeType.PROGRAM: set(),
}


def _placement_error(parent_type, title, parent_title) -> str:
    """The message for a node that _ALLOWED_CHILDREN does not allow under its parent."""
    if parent_type == ProgramRequirementNodeType.PROGRAM_ROOT:
        return (
            "Top-level requirements must be groups, not individual courses or programs."
        )
    if parent_type == ProgramRequirementNodeType.OPERATOR:
        return (
            f"{_group_name(title, parent_title)} is inside a group; only the top "
            "level and tracks can hold groups."
        )
    if parent_type == ProgramRequirementNodeType.TRACK:
        return "A track can only hold groups, not individual courses or programs."
    return "Courses and programs cannot contain other requirements."


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


def _duplicate_errors(name, children) -> list[str]:
    """
    One error per kind of item (course, program) a group lists more than once.
    The evaluator counts each child separately, so a repeated course counts
    twice toward a "Minimum # of".
    """
    items = Counter(
        (data.get("node_type"), data.get("course"), data.get("required_program"))
        for data in (child.get("data", {}) for child in children)
        if data.get("course") or data.get("required_program")
    )
    repeated = sorted({node_type for (node_type, _, _), n in items.items() if n > 1})
    return [f"{name} lists a {node_type} more than once." for node_type in repeated]


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


def _is_track(node) -> bool:
    return node["data"].get("node_type") == ProgramRequirementNodeType.TRACK


def _tracks_container_errors(tree, *, display_mode) -> list[str]:
    """Errors for the top-level groups that hold track nodes."""
    # A track deeper than the top-level groups has its own placement error.
    containers = [
        node for node in tree if any(map(_is_track, node.get("children") or []))
    ]
    errors = []
    if len(containers) > 1:
        errors.append("A program can have only one group of tracks.")
    if containers and display_mode == PROGRAM_DISPLAY_MODE_COURSE:
        errors.append("A program displayed as a course cannot have tracks.")
    for group in containers:
        data = group["data"]
        name = _group_name((data.get("title") or "").strip(), None)
        if data.get("operator") != ProgramRequirement.Operator.MIN_NUMBER_OF:
            errors.append(f'{name} holds tracks, so it must be a "Minimum # of" group.')
        # A learner completes one track, and ProgramEnrollment.track records one.
        elif str(data.get("operator_value")).strip() != "1":
            errors.append(
                f'{name} holds tracks, so its "Minimum # of" Value must be 1.'
            )
        if not all(map(_is_track, group["children"])):
            errors.append(f"{name} holds tracks, so every item in it must be a track.")
        # Program.required_courses and Program.elective_courses bucket every
        # course by the elective_flag of its top-level group; with the flag off,
        # every track course would be listed as required.
        if not data.get("elective_flag"):
            errors.append(f"{name} holds tracks, so it must be an elective group.")
    return errors


def _requires_something(node) -> bool:
    """Whether a node can fail: any leaf, or a group holding items that is not "Minimum # of 0"."""
    data = node["data"]
    if data.get("node_type") != ProgramRequirementNodeType.OPERATOR:
        return True
    accepts_none = (
        data.get("operator") == ProgramRequirement.Operator.MIN_NUMBER_OF
        and str(data.get("operator_value")).strip() == "0"
    )
    return bool(node.get("children")) and not accepts_none


def _track_errors(title, parent_title, children, *, depth) -> list[str]:
    if title:
        name = f'Track "{title}"'
    else:
        name = f'A track in "{parent_title}"' if parent_title else "A track"
    errors = []
    if depth != 3:  # noqa: PLR2004
        errors.append(f'{name} must be inside a top-level "Minimum # of" group.')
    if not title:
        errors.append(f"{name} has no Title.")
    if not any(_requires_something(child) for child in children):
        errors.append(
            f"{name} requires nothing; a track needs a group holding at least one "
            "course or program."
        )
    return errors


def validate_requirement_tree(  # noqa: C901
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
    its number of children; a group lists each course or program once; a
    program displayed as a course requires no programs; and a program requires
    neither itself nor a program that already requires it, which would make
    evaluating either tree recurse forever.

    Tracks sit only at depth 3, inside one top-level elective "Minimum # of 1"
    group that holds nothing else (the tracks container). A track has a title
    and requires at least one course or program: the evaluator treats it as
    all-of, and an all-of with nothing to require is satisfied.

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

    def _visit(node, *, parent_type, parent_title, depth):
        data = node.get("data", {})
        node_type = data.get("node_type")
        title = (data.get("title") or "").strip()
        children = node.get("children") or []

        if node_type == ProgramRequirementNodeType.TRACK:
            errors.extend(_track_errors(title, parent_title, children, depth=depth))
        elif node_type not in _ALLOWED_CHILDREN.get(parent_type, set()):
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
        if node_type == ProgramRequirementNodeType.OPERATOR:
            name = _group_name(title, parent_title)
            if not title:
                errors.append(f"{name} has no Title.")
            if data.get("operator") not in ProgramRequirement.Operator.values:
                errors.append(f'{name} needs an operator: "All of" or "Minimum # of".')
            if data.get("operator") == ProgramRequirement.Operator.MIN_NUMBER_OF:
                errors.extend(_operator_value_errors(name, data, children))
            errors.extend(_duplicate_errors(name, children))
        for child in children:
            _visit(
                child,
                parent_type=node_type,
                parent_title=title or parent_title,
                depth=depth + 1,
            )

    for node in tree:
        _visit(
            node,
            parent_type=ProgramRequirementNodeType.PROGRAM_ROOT,
            parent_title=None,
            depth=2,
        )
    errors.extend(_tracks_container_errors(tree, display_mode=display_mode))

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


def _requirement_root_and_children(program: Program):
    """
    Return the program's requirements root (None if it has none) and each
    node's children, keyed by the parent's materialized path.
    """
    root = None
    children = defaultdict(list)
    for node in _requirement_nodes(program):
        if node.is_root:
            root = node
        else:
            children[node.path[: -ProgramRequirement.steplen]].append(node)
    return root, children


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
    root, children = _requirement_root_and_children(program)
    if root is None:
        return False

    def _satisfied(node):
        # A track is satisfied when all of its groups are.
        if node.is_root or node.is_all_of_operator or node.is_track:
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


@dataclass
class RequirementResult:
    """
    How a learner stands against one node of a program's requirement tree.

    Attributes:
        label: what the node is, e.g. a course's readable id and title.
        satisfied: whether the learner meets this node.
        detail: for a group, how many items are met; for an unmet course or
            program, why it isn't met.
        children: the results for the node's children (and, for a required
            program evaluated through its own tree, that tree's groups).
    """

    label: str
    satisfied: bool
    detail: str = ""
    children: list["RequirementResult"] = field(default_factory=list)

    def unmet_leaves(self) -> list["RequirementResult"]:
        """The unmet courses and programs under this node, in tree order."""
        if self.satisfied:
            return []
        if not self.children:
            return [self]
        return [leaf for child in self.children for leaf in child.unmet_leaves()]

    def format_lines(self, indent: int = 0) -> list[str]:
        """Render this result and its children as indented lines."""
        mark = "✓" if self.satisfied else "✗"
        line = f"{'  ' * indent}{mark} {self.label}"
        if self.detail:
            line = f"{line}: {self.detail}"
        lines = [line]
        for child in self.children:
            lines.extend(child.format_lines(indent + 1))
        return lines


def _group_label(node: ProgramRequirement) -> str:
    title = (node.title or "").strip()
    if node.is_track:
        return f'Track "{title}"' if title else "Track"
    return f'"{title}"' if title else "Group"


def explain_requirement_tree(
    program: Program,
    *,
    explain_leaf: Callable[[ProgramRequirement], RequirementResult],
) -> RequirementResult | None:
    """
    Evaluate the program's requirement tree like is_requirement_tree_satisfied,
    but return each node's result instead of a single bool.

    Groups and tracks are evaluated here, by the same rules; every child is
    evaluated (no short-circuiting), so the result shows everything that's unmet.

    Args:
        program: the program whose tree is evaluated.
        explain_leaf: called with each course or program node; returns its result.

    Returns:
        RequirementResult | None: the root's result, labeled with the program;
        None when the program has no requirements root.
    """
    root, children = _requirement_root_and_children(program)
    if root is None:
        return None

    def _explain(node):
        if node.is_course or node.is_program:
            return explain_leaf(node)
        results = [_explain(child) for child in children[node.path]]
        met = sum(1 for result in results if result.satisfied)
        # Same order as is_requirement_tree_satisfied, so the two always agree.
        if node.is_root or node.is_all_of_operator or node.is_track:
            detail = f"all {len(results)} needed, {met} met"
            satisfied = met == len(results)
        elif node.is_min_number_of_operator:
            needed = int(node.operator_value)
            detail = f"at least {needed} of {len(results)} needed, {met} met"
            satisfied = met >= needed
        else:
            return RequirementResult(
                label=_group_label(node),
                satisfied=False,
                detail="group has no operator, so it can't be met",
                children=results,
            )
        if node.is_root:
            label = f"{program.title} ({program.readable_id})"
        else:
            label = _group_label(node)
        return RequirementResult(
            label=label, satisfied=satisfied, detail=detail, children=results
        )

    return _explain(root)
