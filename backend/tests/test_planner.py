"""Offline tests for model-generated planning."""

import json
from unittest.mock import Mock

import pytest

from careerpilot.config import Settings
from careerpilot.llm import LLMError
from careerpilot.planner import PlanningError, create_plan
from careerpilot.planning import ClarificationPlan, ComparisonPlan


@pytest.fixture
def planner_setup(monkeypatch):
    settings = Settings(
        _env_file=None,
        llm_provider="groq",
        llm_model="test-model",
        llm_api_key="dummy-key",
        llm_timeout_seconds=30,
    )
    generate = Mock()
    monkeypatch.setattr("careerpilot.planner.generate_text", generate)
    return settings, generate


def test_valid_comparison_plan(planner_setup):
    settings, generate = planner_setup
    generate.return_value = json.dumps({
        "decision": {
            "action": "compare",
            "arguments": {
                "current_skills": ["Kotlin"],
                "required_skills": ["Kotlin", "Room"],
            },
            "output": "learning_plan",
        }
    })
    request = (
        "Current: Kotlin. Required: Kotlin, Room. "
        "What should I learn next?"
    )

    plan = create_plan(settings, request)

    assert isinstance(plan.decision, ComparisonPlan)
    assert plan.decision.arguments.required_skills == ["Kotlin", "Room"]
    assert plan.decision.output == "learning_plan"
    generate.assert_called_once()
    sent_settings, sent_prompt = generate.call_args.args
    assert sent_settings is settings
    assert json.dumps(request) in sent_prompt
    assert "PLAN SCHEMA:" in sent_prompt


def test_valid_clarification_plan(planner_setup):
    settings, generate = planner_setup
    generate.return_value = json.dumps({
        "decision": {
            "action": "clarify",
            "question": "What are your current and required skills?",
        }
    })

    plan = create_plan(settings, "Help me prepare for Android jobs.")

    assert isinstance(plan.decision, ClarificationPlan)
    assert plan.decision.question
    generate.assert_called_once()


@pytest.mark.parametrize(
    "raw_plan",
    [
        "not JSON",
        '```json\n{"decision": {"action": "clarify"}}\n```',
        '{"decision": {"action": "run_shell"}}',
        json.dumps({
            "decision": {
                "action": "compare",
                "arguments": {
                    "current_skills": ["Kotlin"],
                    "required_skills": [],
                },
                "output": "explanation",
            }
        }),
    ],
)
def test_invalid_model_output_is_rejected(planner_setup, raw_plan):
    settings, generate = planner_setup
    generate.return_value = raw_plan

    with pytest.raises(PlanningError, match="invalid plan"):
        create_plan(settings, "Compare my skills.")

    generate.assert_called_once()


def test_blank_request_does_not_call_model(planner_setup):
    settings, generate = planner_setup

    with pytest.raises(ValueError, match="blank"):
        create_plan(settings, "   ")

    generate.assert_not_called()


def test_llm_error_propagates_without_retry(planner_setup):
    settings, generate = planner_setup
    generate.side_effect = LLMError("Could not connect to Groq.")

    with pytest.raises(LLMError, match="connect"):
        create_plan(settings, "Compare my skills.")

    generate.assert_called_once()