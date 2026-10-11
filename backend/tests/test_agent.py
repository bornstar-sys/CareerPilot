"""Offline tests for the complete agent workflow."""

import json
from unittest.mock import Mock

import pytest

from careerpilot.agent import run_agent
from careerpilot.config import Settings
from careerpilot.execution import ExecutionError
from careerpilot.llm import LLMError
from careerpilot.planner import PlanningError
from careerpilot.planning import AgentPlan
from careerpilot.tools import CompareSkillsInput


@pytest.fixture
def agent_setup(monkeypatch):
    settings = Settings(
        _env_file=None,
        llm_provider="groq",
        llm_model="test-model",
        llm_api_key="dummy-key",
        llm_timeout_seconds=30,
    )
    planner = Mock()
    writer = Mock(return_value="Kotlin matches. Consider learning Room.")

    monkeypatch.setattr("careerpilot.agent.create_plan", planner)
    monkeypatch.setattr("careerpilot.agent.generate_text", writer)

    return settings, planner, writer


def comparison_plan(output="explanation", current=None):
    return AgentPlan.model_validate({
        "decision": {
            "action": "compare",
            "arguments": {
                "current_skills": ["Kotlin"] if current is None else current,
                "required_skills": ["Kotlin", "Room"],
            },
            "output": output,
        }
    })


@pytest.mark.parametrize("output", ["explanation", "learning_plan"])
def test_comparison_passes_real_evidence_to_writer(agent_setup, output):
    settings, planner, writer = agent_setup
    planner.return_value = comparison_plan(output)
    supplied = CompareSkillsInput(
        current_skills=["Kotlin"],
        required_skills=["Kotlin", "Room"],
    )

    result = run_agent(
        settings,
        "Help me compare these skills.",
        supplied_skills=supplied,
    )

    assert result.execution.status == "compared"
    assert result.execution.tool_result["missing_skills"] == ["Room"]
    assert result.answer == writer.return_value
    planner.assert_called_once()
    writer.assert_called_once()

    planner_prompt = planner.call_args.args[1]
    assert supplied.model_dump_json() in planner_prompt

    answer_prompt = writer.call_args.args[1]
    evidence = json.loads(answer_prompt.split("EVIDENCE:\n", 1)[1])
    assert evidence["supplied_skills"] == supplied.model_dump()
    assert evidence["comparison_result"] == result.execution.tool_result
    if output == "learning_plan":
        assert "practical exercise" in answer_prompt


def test_clarification_skips_response_generation(agent_setup):
    settings, planner, writer = agent_setup
    planner.return_value = AgentPlan.model_validate({
        "decision": {
            "action": "clarify",
            "question": "What are your current and required skills?",
        }
    })

    result = run_agent(settings, "Help me prepare for Android jobs.")

    assert result.execution.status == "needs_input"
    assert result.answer == "What are your current and required skills?"
    planner.assert_called_once()
    writer.assert_not_called()


def test_changed_skills_stop_before_response_generation(agent_setup):
    settings, planner, writer = agent_setup
    planner.return_value = comparison_plan(current=["Kotlin", "Python"])
    supplied = CompareSkillsInput(
        current_skills=["Kotlin"],
        required_skills=["Kotlin", "Room"],
    )

    with pytest.raises(ExecutionError, match="do not match"):
        run_agent(settings, "Compare these.", supplied_skills=supplied)

    writer.assert_not_called()


def test_planning_failure_stops_workflow(agent_setup):
    settings, planner, writer = agent_setup
    planner.side_effect = PlanningError("Invalid plan.")

    with pytest.raises(PlanningError):
        run_agent(settings, "Compare these.")

    planner.assert_called_once()
    writer.assert_not_called()


def test_response_failure_propagates_without_retry(agent_setup):
    settings, planner, writer = agent_setup
    planner.return_value = comparison_plan()
    writer.side_effect = LLMError("Could not connect to Groq.")
    supplied = CompareSkillsInput(
        current_skills=["Kotlin"],
        required_skills=["Kotlin", "Room"],
    )

    with pytest.raises(LLMError, match="connect"):
        run_agent(settings, "Compare these.", supplied_skills=supplied)

    planner.assert_called_once()
    writer.assert_called_once()


def test_blank_request_stops_before_planning(agent_setup):
    settings, planner, writer = agent_setup

    with pytest.raises(ValueError, match="blank"):
        run_agent(settings, "   ")

    planner.assert_not_called()
    writer.assert_not_called()


def test_missing_supplied_skills_stops_before_answer(agent_setup):
    settings, planner, writer = agent_setup
    planner.return_value = comparison_plan()

    with pytest.raises(ExecutionError, match="independently supplied"):
        run_agent(settings, "Current: Kotlin. Required: Kotlin, Room.")

    planner.assert_called_once()
    writer.assert_not_called()


def test_tool_failure_stops_before_answer(agent_setup, monkeypatch):
    settings, planner, writer = agent_setup
    planner.return_value = comparison_plan()
    tool = Mock(side_effect=RuntimeError("Comparison failed."))
    monkeypatch.setattr("careerpilot.execution.compare_skills", tool)

    supplied = CompareSkillsInput(
        current_skills=["Kotlin"],
        required_skills=["Kotlin", "Room"],
    )

    with pytest.raises(RuntimeError, match="Comparison failed"):
        run_agent(settings, "Compare these.", supplied_skills=supplied)

    planner.assert_called_once()
    tool.assert_called_once()
    writer.assert_not_called()