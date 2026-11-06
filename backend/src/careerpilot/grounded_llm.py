"""One bounded Groq call for selecting document evidence.

Separate from the Phase 1 client so its existing public behavior stays intact.
The existing validated Settings object is accepted; no settings are loaded here.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from careerpilot.grounding import SYSTEM_PROMPT

if TYPE_CHECKING:
    from careerpilot.config import Settings


class DocumentLLMError(RuntimeError):
    """Safe-to-display document-generation failure; never raw provider bodies."""


def generate_evidence_selection(settings: Settings, prompt: str) -> str:
    if settings.llm_provider != 'groq':
        raise ValueError('Document generation currently supports only groq.')
    if settings.llm_api_key is None:
        raise ValueError('A Groq API key is required for live document generation.')
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 60000:
        raise ValueError('Document prompt is empty or too large.')
    from groq import APIConnectionError, APIStatusError, Groq

    kwargs = dict(
        model=settings.llm_model,
        messages=[{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': prompt}],
        response_format={'type': 'json_object'},
        max_completion_tokens=2048,
    )
    if settings.llm_model.startswith('openai/gpt-oss-'):
        kwargs['reasoning_effort'] = 'low'
    try:
        with Groq(api_key=settings.llm_api_key.get_secret_value(),
                  timeout=float(settings.llm_timeout_seconds), max_retries=0) as client:
            response = client.chat.completions.create(**kwargs)
    except APIStatusError as exc:
        raise DocumentLLMError(f'Groq rejected the document request (HTTP {exc.status_code}).') from None
    except APIConnectionError:
        raise DocumentLLMError('Could not connect to Groq within the configured timeout.') from None
    if not response.choices or response.choices[0].finish_reason != 'stop':
        raise DocumentLLMError('Groq did not return a completed document response.')
    text = response.choices[0].message.content
    if not isinstance(text, str) or not text.strip():
        raise DocumentLLMError('Groq returned an empty document response.')
    return text.strip()
