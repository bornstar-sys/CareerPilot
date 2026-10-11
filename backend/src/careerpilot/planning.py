"""Validated planning decisions for CareerPilot."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from careerpilot.tools import CompareSkillsInput


QuestionText = Annotated[
    str,
    StringConstraints(
        strict=True,
        strip_whitespace=True,
        min_length=1,
        max_length=500,
    ),
]


class ClarificationPlan(BaseModel):
    """Ask for missing information before using a tool."""

    model_config = ConfigDict(extra="forbid")

    action: Literal["clarify"]
    question: QuestionText


class ComparisonPlan(BaseModel):
    """Compare explicit skill lists, then produce the requested output."""

    model_config = ConfigDict(extra="forbid")

    action: Literal["compare"]
    arguments: CompareSkillsInput
    output: Literal["explanation", "learning_plan"]


class AgentPlan(BaseModel):
    """One validated decision proposed by the planner."""

    model_config = ConfigDict(extra="forbid")

    decision: Annotated[
        ClarificationPlan | ComparisonPlan,
        Field(discriminator="action"),
    ]