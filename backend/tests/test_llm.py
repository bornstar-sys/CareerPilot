"""Offline tests for the Groq text client."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from groq import APIConnectionError, APIStatusError

from careerpilot.config import Settings
from careerpilot.llm import LLMError, generate_text


@pytest.fixture
def setup_client(monkeypatch):
    settings = Settings(
        _env_file=None,
        llm_provider="groq",
        llm_model="test-model",
        llm_api_key="dummy-key-for-tests-only",
        llm_timeout_seconds=30,
    )

    constructor = MagicMock()
    client = constructor.return_value.__enter__.return_value
    monkeypatch.setattr("careerpilot.llm.Groq", constructor)

    return settings, constructor, client


def make_response(text="  Hello  ", finish_reason="stop"):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=text),
                finish_reason=finish_reason,
            )
        ]
    )


def test_generation_uses_settings_and_closes_client(setup_client):
    settings, constructor, client = setup_client
    client.chat.completions.create.return_value = make_response()

    assert generate_text(settings, "Hello") == "Hello"

    constructor.assert_called_once_with(
        api_key="dummy-key-for-tests-only",
        timeout=30.0,
        max_retries=0,
    )
    client.chat.completions.create.assert_called_once_with(
        model="test-model",
        messages=[{"role": "user", "content": "Hello"}],
        max_completion_tokens=1024,
    )
    constructor.return_value.__exit__.assert_called_once()


def test_blank_prompt_makes_no_request(setup_client):
    settings, constructor, _ = setup_client

    with pytest.raises(ValueError, match="blank"):
        generate_text(settings, "   ")

    constructor.assert_not_called()


@pytest.mark.parametrize(
    "response",
    [
        SimpleNamespace(choices=[]),
        make_response(text=None),
        make_response(text="   "),
        make_response(text="Partial answer", finish_reason="length"),
    ],
)
def test_unusable_response_is_rejected(setup_client, response):
    settings, _, client = setup_client
    client.chat.completions.create.return_value = response

    with pytest.raises(LLMError):
        generate_text(settings, "Hello")


@pytest.mark.parametrize("status", [401, 429, 500])
def test_http_errors_do_not_expose_provider_details(setup_client, status):
    settings, _, client = setup_client
    request = httpx.Request("POST", "https://api.groq.com")
    response = httpx.Response(status, request=request)

    client.chat.completions.create.side_effect = APIStatusError(
        "Sensitive provider detail: dummy-key-for-tests-only",
        response=response,
        body=None,
    )

    with pytest.raises(LLMError) as caught:
        generate_text(settings, "Hello")

    assert str(status) in str(caught.value)
    assert "dummy-key" not in str(caught.value)


def test_connection_failure_is_reported(setup_client):
    settings, _, client = setup_client
    client.chat.completions.create.side_effect = APIConnectionError(
        request=httpx.Request("POST", "https://api.groq.com")
    )

    with pytest.raises(LLMError, match="connect"):
        generate_text(settings, "Hello")