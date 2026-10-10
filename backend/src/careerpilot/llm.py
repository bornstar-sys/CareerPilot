"""Text generation through Groq."""

from groq import APIConnectionError, APIStatusError, Groq

from careerpilot.config import Settings


class LLMError(RuntimeError):
    """A safe-to-display failure during text generation."""


def generate_text(settings: Settings, prompt: str) -> str:
    """Generate a complete text response using validated configuration."""
    if settings.llm_provider != "groq":
        raise ValueError("This client currently supports only groq.")

    if not prompt.strip():
        raise ValueError("Prompt must not be blank.")

    if settings.llm_api_key is None:
        raise ValueError("A Groq API key is required.")

    try:
        with Groq(
            api_key=settings.llm_api_key.get_secret_value(),
            timeout=float(settings.llm_timeout_seconds),
            max_retries=0,
        ) as client:
            response = client.chat.completions.create(
                model=settings.llm_model,
                messages=[{"role": "user", "content": prompt}],
                max_completion_tokens=1024,
            )
    except APIStatusError as exc:
        raise LLMError(
            f"Groq rejected the request (HTTP {exc.status_code})."
        ) from None
    except APIConnectionError:
        raise LLMError(
            "Could not connect to Groq within the configured timeout."
        ) from None

    if not response.choices:
        raise LLMError("Groq returned no response choices.")

    choice = response.choices[0]

    if choice.finish_reason != "stop":
        raise LLMError(
            "Groq did not return a completed text response."
        )

    text = (choice.message.content or "").strip()
    if not text:
        raise LLMError("Groq returned an empty text response.")

    return text