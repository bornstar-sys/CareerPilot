from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
import pytest
from groq import APIConnectionError, APIStatusError

from careerpilot.grounded_llm import DocumentLLMError, generate_evidence_selection
from careerpilot.grounding import SYSTEM_PROMPT


@pytest.fixture
def settings():
    key = SimpleNamespace(get_secret_value=lambda: 'fake-test-key')
    return SimpleNamespace(llm_provider='groq', llm_model='openai/gpt-oss-120b',
                           llm_api_key=key, llm_timeout_seconds=20)


@pytest.fixture
def provider():
    with patch('groq.Groq') as factory:
        client = MagicMock()
        factory.return_value.__enter__.return_value = client
        client.chat.completions.create.return_value = SimpleNamespace(choices=[
            SimpleNamespace(finish_reason='stop', message=SimpleNamespace(
                content=' {"status":"insufficient_evidence","evidence":[]} '))])
        yield factory, client


def test_bounded_call_separates_rules_from_untrusted_data(settings, provider):
    factory, client = provider
    result = generate_evidence_selection(settings, '{"question":"offline?","passages":[]}')
    assert result.startswith('{')
    factory.assert_called_once_with(api_key='fake-test-key', timeout=20.0, max_retries=0)
    client.chat.completions.create.assert_called_once()
    args = client.chat.completions.create.call_args.kwargs
    assert args['messages'] == [{'role': 'system', 'content': SYSTEM_PROMPT},
        {'role': 'user', 'content': '{"question":"offline?","passages":[]}'}]
    assert args['response_format'] == {'type': 'json_object'}
    assert args['max_completion_tokens'] == 2048
    assert args['reasoning_effort'] == 'low'
    assert 'tools' not in args


def test_non_gpt_oss_model_does_not_receive_reasoning_option(settings, provider):
    settings.llm_model = 'test-other-model'
    generate_evidence_selection(settings, '{}')
    assert 'reasoning_effort' not in provider[1].chat.completions.create.call_args.kwargs


@pytest.mark.parametrize('kind', ['provider', 'missing-key', 'empty-prompt', 'long-prompt'])
def test_invalid_configuration_before_network(settings, provider, kind):
    prompt = '{}'
    if kind == 'provider': settings.llm_provider = 'other'
    if kind == 'missing-key': settings.llm_api_key = None
    if kind == 'empty-prompt': prompt = ' '
    if kind == 'long-prompt': prompt = 'x' * 60001
    with pytest.raises(ValueError):
        generate_evidence_selection(settings, prompt)
    provider[0].assert_not_called()


@pytest.mark.parametrize('status', [400, 429, 503])
def test_http_errors_do_not_expose_provider_bodies_or_retry(settings, provider, status):
    response = httpx.Response(status, request=httpx.Request('POST', 'https://api.example.test'))
    provider[1].chat.completions.create.side_effect = APIStatusError(
        'private-body fake-test-key', response=response, body={'private': 'secret'})
    with pytest.raises(DocumentLLMError) as error:
        generate_evidence_selection(settings, '{}')
    assert str(status) in str(error.value)
    assert 'private' not in str(error.value) and 'fake-test-key' not in str(error.value)
    provider[1].chat.completions.create.assert_called_once()


def test_connection_error_is_safe(settings, provider):
    provider[1].chat.completions.create.side_effect = APIConnectionError(
        request=httpx.Request('POST', 'https://api.example.test'))
    with pytest.raises(DocumentLLMError, match='Could not connect'):
        generate_evidence_selection(settings, '{}')


@pytest.mark.parametrize('reason,content', [('length', '{}'), ('tool_calls', None),
                                         ('stop', ''), ('stop', None)],
                         ids=['truncated', 'tool-request', 'empty', 'missing'])
def test_incomplete_or_empty_output_is_not_an_answer(settings, provider, reason, content):
    provider[1].chat.completions.create.return_value.choices = [
        SimpleNamespace(finish_reason=reason, message=SimpleNamespace(content=content))]
    with pytest.raises(DocumentLLMError):
        generate_evidence_selection(settings, '{}')


def test_missing_choices(settings, provider):
    provider[1].chat.completions.create.return_value.choices = []
    with pytest.raises(DocumentLLMError):
        generate_evidence_selection(settings, '{}')
