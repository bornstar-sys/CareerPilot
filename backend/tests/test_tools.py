"""Offline tests for CareerPilot tools."""

import pytest
from pydantic import ValidationError

from careerpilot.tools import CompareSkillsInput, compare_skills


def test_identifies_matched_and_missing_skills():
    arguments = CompareSkillsInput(
        current_skills=["Kotlin", "Jetpack Compose"],
        required_skills=["Kotlin", "Room", "REST API"],
    )

    assert compare_skills(arguments) == {
        "matched_skills": ["Kotlin"],
        "missing_skills": ["Room", "REST API"],
        "matched_count": 1,
        "required_count": 3,
    }


def test_normalizes_case_spaces_and_duplicates():
    arguments = CompareSkillsInput(
        current_skills=[" kotlin ", "KOTLIN"],
        required_skills=[" Kotlin ", "kotlin", "Room", "ROOM"],
    )

    assert compare_skills(arguments) == {
        "matched_skills": ["Kotlin"],
        "missing_skills": ["Room"],
        "matched_count": 1,
        "required_count": 2,
    }


def test_empty_current_skills_means_all_required_are_missing():
    arguments = CompareSkillsInput(
        current_skills=[],
        required_skills=["SQL"],
    )

    assert compare_skills(arguments)["missing_skills"] == ["SQL"]


@pytest.mark.parametrize(
    "payload",
    [
        {"current_skills": [], "required_skills": []},
        {"current_skills": ["   "], "required_skills": ["SQL"]},
        {"current_skills": [123], "required_skills": ["SQL"]},
        {
            "current_skills": [],
            "required_skills": ["SQL"],
            "unexpected": True,
        },
    ],
)
def test_invalid_arguments_are_rejected(payload):
    with pytest.raises(ValidationError):
        CompareSkillsInput.model_validate(payload)