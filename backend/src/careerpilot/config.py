"""Validated configuration for CareerPilot."""

from pathlib import Path
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CAREERPILOT_",
        env_file=None,
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="forbid",
        hide_input_in_errors=True,
        frozen=True,
    )

    app_env: Literal["development", "test", "production"] = "development"
    llm_provider: Literal["mock", "openai", "gemini", "anthropic", "groq"] = "mock"
    llm_model: str = ""
    llm_api_key: SecretStr | None = Field(
        default=None,
        repr=False,
        exclude=True,
    )
    llm_timeout_seconds: int = Field(default=30, ge=1, le=120)

    @model_validator(mode="after")
    def validate_live_provider(self) -> Self:
        if self.llm_provider == "mock":
            return self

        if not self.llm_model.strip():
            raise ValueError(
                "CAREERPILOT_LLM_MODEL is required for a live provider."
            )

        if (
            self.llm_api_key is None
            or not self.llm_api_key.get_secret_value().strip()
        ):
            raise ValueError(
                "CAREERPILOT_LLM_API_KEY is required for a live provider."
            )

        return self


def load_settings(env_file: Path | None = None) -> Settings:
    """Load environment variables and an explicitly selected dotenv file."""
    if env_file is not None and not env_file.is_file():
        raise FileNotFoundError(f"Configuration file not found: {env_file}")

    return Settings(_env_file=env_file)
