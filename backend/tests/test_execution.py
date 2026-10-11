"""Offline verification of plan execution."""

from unittest.mock import Mock

import pytest

from careerpilot.execution import ExecutionError, execute_plan
from careerpilot.planning import AgentPlan
from careerpilot.tools import CompareSkillsInput


def comparison_plan(current_skills, required_skills):
    return AgentPlan.model_validate({
        "decision": {
            "action": "compare",
            "arguments": {
                "current_skills": current_skills,
                "required_skills": required_skills,
            },
            "output": "learning_plan",
        }
    })


def test_clarification_returns_question_without_tool(monkeypatch):
    tool = Mock()
    monkeypatch.setattr("careerpilot.execution.compare_skills", tool)
    plan = AgentPlan.model_validate({
        "decision": {
            "action": "clarify",
            "question": "What skills does the job require?",
        }
    })

    result = execute_plan(plan)

    assert result.status == "needs_input"
    assert result.question == "What skills does the job require?"
    assert result.tool_result is None
    tool.assert_not_called()


def test_comparison_returns_real_tool_result():
    supplied = CompareSkillsInput(
        current_skills=["Kotlin"],
        required_skills=["Kotlin", "Room"],
    )
    plan = comparison_plan(["Kotlin"], ["Kotlin", "Room"])

    result = execute_plan(plan, supplied_skills=supplied)

    assert result.status == "compared"
    assert result.question is None
    assert result.tool_result == {
        "matched_skills": ["Kotlin"],
        "missing_skills": ["Room"],
        "matched_count": 1,
        "required_count": 2,
    }


def test_missing_supplied_skills_blocks_tool(monkeypatch):
    tool = Mock()
    monkeypatch.setattr("careerpilot.execution.compare_skills", tool)
    plan = comparison_plan(["Kotlin"], ["Room"])

    with pytest.raises(ExecutionError, match="independently supplied"):
        execute_plan(plan)

    tool.assert_not_called()


@pytest.mark.parametrize(
    ("planned_current", "planned_required"),
    [
        (["Kotlin", "Python"], ["Kotlin", "Room"]),
        (["Kotlin"], ["Kotlin", "Room", "Docker"]),
        (["Kotlin"], ["Kotlin"]),
    ],
)
def test_changed_skill_lists_block_tool(
    monkeypatch, planned_current, planned_required
):
    tool = Mock()
    monkeypatch.setattr("careerpilot.execution.compare_skills", tool)
    supplied = CompareSkillsInput(
        current_skills=["Kotlin"],
        required_skills=["Kotlin", "Room"],
    )
    plan = comparison_plan(planned_current, planned_required)

    with pytest.raises(ExecutionError, match="do not match"):
        execute_plan(plan, supplied_skills=supplied)

    tool.assert_not_called()


def test_explicitly_empty_current_skills_can_execute():
    supplied = CompareSkillsInput(
        current_skills=[],
        required_skills=["Kotlin"],
    )
    plan = comparison_plan([], ["Kotlin"])

    result = execute_plan(plan, supplied_skills=supplied)

    assert result.status == "compared"
    assert result.tool_result["missing_skills"] == ["Kotlin"]
    assert result.tool_result["matched_count"] == 0