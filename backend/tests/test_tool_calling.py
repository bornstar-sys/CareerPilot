"""Offline verification of the tool-call round trip."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from careerpilot.config import Settings
from careerpilot.llm import LLMError
from careerpilot.tool_calling import run_skill_comparison


def response(message, finish_reason):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(message=message, finish_reason=finish_reason)
        ]
    )


@pytest.fixture
def setup_flow(monkeypatch):
    settings = Settings(
        _env_file=None,
        llm_provider="groq",
        llm_model="test-model",
        llm_api_key="dummy-key",
        llm_timeout_seconds=30,
    )
    constructor = MagicMock()
    client = constructor.return_value.__enter__.return_value
    monkeypatch.setattr("careerpilot.tool_calling.Groq", constructor)

    call = SimpleNamespace(
        id="call_test_1",
        type="function",
        function=SimpleNamespace(
            name="compare_skills",
            arguments=json.dumps({
                "current_skills": ["Kotlin"],
                "required_skills": ["Kotlin", "Room"],
            }),
        ),
    )
    first = response(
        SimpleNamespace(content=None, tool_calls=[call]),
        "tool_calls",
    )
    final = response(
        SimpleNamespace(
            content="Kotlin matches. Room is missing from your list.",
            tool_calls=None,
        ),
        "stop",
    )
    client.chat.completions.create.side_effect = [first, final]

    return settings, client, call, final


def test_round_trip_sends_real_tool_result_with_matching_id(setup_flow):
    settings, client, _, _ = setup_flow

    result = run_skill_comparison(
        settings,
        "Current: Kotlin. Required: Kotlin, Room.",
    )

    assert result.tool_result["missing_skills"] == ["Room"]
    assert result.arguments.current_skills == ["Kotlin"]
    assert result.answer
    assert client.chat.completions.create.call_count == 2

    sent = client.chat.completions.create.call_args_list[1].kwargs
    tool_message = sent["messages"][-1]

    assert tool_message["role"] == "tool"
    assert tool_message["tool_call_id"] == "call_test_1"
    assert json.loads(tool_message["content"]) == result.tool_result
    assert sent["tool_choice"] == "none"


@pytest.mark.parametrize(
    "arguments",
    [
        "not valid JSON",
        '{"current_skills": [], "required_skills": []}',
    ],
)
def test_invalid_arguments_stop_before_second_request(setup_flow, arguments):
    settings, client, call, _ = setup_flow
    call.function.arguments = arguments

    with pytest.raises(LLMError, match="validation"):
        run_skill_comparison(settings, "Compare my skills.")

    assert client.chat.completions.create.call_count == 1


def test_unknown_tool_is_rejected(setup_flow):
    settings, client, call, _ = setup_flow
    call.function.name = "unknown_tool"

    with pytest.raises(LLMError, match="unsupported"):
        run_skill_comparison(settings, "Compare my skills.")

    assert client.chat.completions.create.call_count == 1


def test_truncated_explanation_is_rejected(setup_flow):
    settings, client, _, final = setup_flow
    final.choices[0].finish_reason = "length"

    with pytest.raises(LLMError, match="finish"):
        run_skill_comparison(settings, "Compare my skills.")

    assert client.chat.completions.create.call_count == 2