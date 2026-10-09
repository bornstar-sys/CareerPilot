"""Tests for configuration validation and secret handling."""

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from careerpilot.config import Settings, load_settings


@pytest.fixture(autouse=True)
def isolate_environment(monkeypatch):
    for name in list(os.environ):
        if name.upper().startswith("CAREERPILOT_"):
            monkeypatch.delenv(name)


def test_defaults_need_no_api_key():
    settings = load_settings()

    assert settings.llm_provider == "mock"
    assert settings.llm_api_key is None


def test_dotenv_loading_and_environment_override(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "CAREERPILOT_LLM_TIMEOUT_SECONDS=45\n",
        encoding="utf-8",
    )

    assert load_settings(env_file).llm_timeout_seconds == 45

    monkeypatch.setenv("CAREERPILOT_LLM_TIMEOUT_SECONDS", "60")

    assert load_settings(env_file).llm_timeout_seconds == 60


def test_live_provider_requires_model():
    with pytest.raises(ValidationError, match="LLM_MODEL"):
        Settings(llm_provider="openai")


@pytest.mark.parametrize("key", [None, "", "   "])
def test_live_provider_requires_nonblank_key(key):
    with pytest.raises(ValidationError, match="LLM_API_KEY"):
        Settings(
            llm_provider="openai",
            llm_model="test-model",
            llm_api_key=key,
        )


def test_key_is_excluded_from_representation_and_serialization():
    dummy_key = "dummy-key-for-tests-only"
    settings = Settings(
        llm_provider="openai",
        llm_model="test-model",
        llm_api_key=dummy_key,
    )

    assert dummy_key not in repr(settings)
    assert "llm_api_key" not in settings.model_dump()
    assert dummy_key not in settings.model_dump_json()


def test_invalid_timeout_is_rejected():
    with pytest.raises(ValidationError):
        Settings(llm_timeout_seconds=0)


def test_unknown_provider_is_rejected():
    with pytest.raises(ValidationError):
        Settings(llm_provider="unsupported")


def test_missing_dotenv_file_is_reported(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_settings(tmp_path / "missing.env")


def test_typo_in_dotenv_is_rejected(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "CAREERPILOT_LLM_TIMOUT_SECONDS=30\n",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        load_settings(env_file)
