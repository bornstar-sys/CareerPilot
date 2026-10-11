"""Execute a plan using independently supplied skill lists."""

from dataclasses import dataclass
from typing import Literal

from careerpilot.planning import AgentPlan, ClarificationPlan
from careerpilot.tools import CompareSkillsInput, compare_skills


class ExecutionError(RuntimeError):
    """A plan could not be executed safely."""


@dataclass(frozen=True)
class ExecutionResult:
    """The outcome of the deterministic execution stage."""

    status: Literal["needs_input", "compared"]
    question: str | None = None
    tool_result: dict[str, object] | None = None


def execute_plan(
    plan: AgentPlan,
    *,
    supplied_skills: CompareSkillsInput | None = None,
) -> ExecutionResult:
    """Ask for information or execute one verified comparison."""
    # Revalidate at the execution boundary, including nested fields.
    validated_plan = AgentPlan.model_validate(plan.model_dump())
    decision = validated_plan.decision

    if isinstance(decision, ClarificationPlan):
        return ExecutionResult(
            status="needs_input",
            question=decision.question,
        )

    if supplied_skills is None:
        raise ExecutionError(
            "Comparison requires independently supplied skill lists."
        )

    validated_skills = CompareSkillsInput.model_validate(
        supplied_skills.model_dump()
    )

    if decision.arguments.model_dump() != validated_skills.model_dump():
        raise ExecutionError(
            "Planned skills do not match the supplied skill lists."
        )

    return ExecutionResult(
        status="compared",
        tool_result=compare_skills(validated_skills),
    )