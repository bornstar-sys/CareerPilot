"""Validated, deterministic tools for CareerPilot."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


SkillName = Annotated[
    str,
    StringConstraints(
        strict=True,
        strip_whitespace=True,
        min_length=1,
        max_length=100,
    ),
]


class CompareSkillsInput(BaseModel):
    """Arguments accepted by the skill comparison tool."""

    model_config = ConfigDict(extra="forbid")

    current_skills: list[SkillName] = Field(
        max_length=50,
        description="Skills explicitly supplied as the user's current skills.",
    )
    required_skills: list[SkillName] = Field(
        min_length=1,
        max_length=50,
        description="Required skills explicitly supplied for comparison.",
    )


def compare_skills(arguments: CompareSkillsInput) -> dict[str, object]:
    """Compare names case-insensitively, preserving required-skill order."""
    current = {
        skill.casefold()
        for skill in arguments.current_skills
    }

    # Deduplicate required skills while keeping their first spelling.
    required: dict[str, str] = {}
    for skill in arguments.required_skills:
        required.setdefault(skill.casefold(), skill)

    matched = [
        name for normalized, name in required.items()
        if normalized in current
    ]
    missing = [
        name for normalized, name in required.items()
        if normalized not in current
    ]

    return {
        "matched_skills": matched,
        "missing_skills": missing,
        "matched_count": len(matched),
        "required_count": len(required),
    }