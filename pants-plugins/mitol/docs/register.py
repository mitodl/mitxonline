import logging
from dataclasses import dataclass

from pants.backend.python.target_types import ConsoleScript
from pants.backend.python.util_rules.interpreter_constraints import (
    InterpreterConstraints,
)
from pants.backend.python.util_rules.pex import (
    Pex,
    PexProcess,
    PexRequest,
    PexRequirements,
)
from pants.core.util_rules.distdir import DistDir
from pants.engine.fs import Digest, MergeDigests, PathGlobs, Workspace
from pants.engine.goal import Goal, GoalSubsystem
from pants.engine.process import FallibleProcessResult
from pants.engine.rules import Get, collect_rules, goal_rule
from pants.engine.target import (
    COMMON_TARGET_FIELDS,
    FieldSet,
    StringField,
    Target,
    Targets,
)

logger = logging.getLogger(__name__)


class DocsGoalSubsystem(GoalSubsystem):
    name = "docs"
    help = "Generate documentation"


class Docs(Goal):
    subsystem_cls = DocsGoalSubsystem
    environment_behavior = None


class SphinxSources(StringField):
    alias = "source_directory"


@dataclass(frozen=True)
class SphinxDocsFieldSet(FieldSet):
    required_fields = (SphinxSources,)
    source_directory: SphinxSources


class SphinxDocs(Target):
    alias = "sphinx_docs"
    core_fields = (*COMMON_TARGET_FIELDS, SphinxSources)
    help = "Define a sphinx docs source"


@goal_rule
async def build_docs(targets: Targets, dist_dir: DistDir, workspace: Workspace) -> Docs:
    pex = await Get(
        Pex,
        PexRequest(
            output_filename="sphinx-build.pex",
            internal_only=True,
            requirements=PexRequirements(
                [
                    "sphinx",
                    "insipid-sphinx-theme",
                    "sphinxcontrib-mermaid",
                    "myst_parser",
                ]
            ),
            interpreter_constraints=InterpreterConstraints([">=3.6"]),
            main=ConsoleScript("sphinx-build"),
        ),
    )
    digests = []

    for target in targets:
        if not SphinxDocsFieldSet.is_applicable(target):
            continue
        source_dir = f"{target.address.spec_path}/{target.get(SphinxSources).value}"
        output_path = "sphinx"

        digest = await Get(Digest, PathGlobs([f"{source_dir}/**/*"]))
        result = await Get(
            FallibleProcessResult,
            PexProcess(
                pex,
                argv=[source_dir, output_path],
                description="Generate sphinx docs",
                input_digest=digest,
                output_directories=[output_path],
            ),
        )
        digests.append(result.output_digest)
        logger.info(result.stdout.decode())
        logger.info(result.stderr.decode())

    merged_digest = await Get(Digest, MergeDigests(digests))

    workspace.write_digest(merged_digest, path_prefix=str(dist_dir.relpath))
    return Docs(exit_code=0)


def target_types():
    return [SphinxDocs]


def rules():
    return collect_rules()
