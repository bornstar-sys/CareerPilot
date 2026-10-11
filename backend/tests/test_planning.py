"""Offline tests for the planning contract."""

import json

import pytest
from pydantic import ValidationError

from careerpilot.planning import (
    AgentPlan,
    ClarificationPlan,
    ComparisonPlan,
)


def test_comparison_plan_reuses_skill_validation():
    plan = AgentPlan.model_validate({
        "decision": {
            "action": "compare",
            "arguments": {
                "current_skills": [" Kotlin "],
                "required_skills": ["Kotlin", "Room"],
            },
            "output": "learning_plan",
        }
    })

    assert isinstance(plan.decision, ComparisonPlan)
    assert plan.decision.arguments.current_skills == ["Kotlin"]
    assert plan.decision.arguments.required_skills == ["Kotlin", "Room"]
    assert plan.decision.output == "learning_plan"


def test_clarification_plan_accepts_a_question():
    plan = AgentPlan.model_validate({
        "decision": {
            "action": "clarify",
            "question": " What skills do you currently have? ",
        }
    })

    assert isinstance(plan.decision, ClarificationPlan)
    assert plan.decision.question == "What skills do you currently have?"


def test_explicitly_empty_current_skills_are_valid():
    plan = AgentPlan.model_validate({
        "decision": {
            "action": "compare",
            "arguments": {
                "current_skills": [],
                "required_skills": ["Kotlin"],
            },
            "output": "explanation",
        }
    })

    assert plan.decision.arguments.current_skills == []


def test_plan_can_be_parsed_from_json():
    payload = {
        "decision": {
            "action": "compare",
            "arguments": {
                "current_skills": ["Kotlin"],
                "required_skills": ["Room"],
            },
            "output": "explanation",
        }
    }

    plan = AgentPlan.model_validate_json(json.dumps(payload))

    assert plan.model_dump() == payload


@pytest.mark.parametrize(
    "decision",
    [
        # Unsupported action.
        {"action": "run_shell", "command": "echo hello"},
        # Blank clarification.
        {"action": "clarify", "question": "   "},
        # Clarification must not include executable arguments.
        {
            "action": "clarify",
            "question": "What are your skills?",
            "arguments": {
                "current_skills": [],
                "required_skills": ["Kotlin"],
            },
        },
        # Required skills must not be empty.
        {
            "action": "compare",
            "arguments": {
                "current_skills": ["Kotlin"],
                "required_skills": [],
            },
            "output": "explanation",
        },
        # Missing current skills must not silently become an empty list.
        {
            "action": "compare",
            "arguments": {"required_skills": ["Kotlin"]},
            "output": "explanation",
        },
        # Unsupported output type.
        {
            "action": "compare",
            "arguments": {
                "current_skills": ["Kotlin"],
                "required_skills": ["Room"],
            },
            "output": "apply_for_jobs",
        },
    ],
)
def test_invalid_decisions_are_rejected(decision):
    with pytest.raises(ValidationError):
        AgentPlan.model_validate({"decision": decision})