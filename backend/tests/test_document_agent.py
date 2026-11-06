import json
from unittest.mock import Mock, patch

import pytest

from careerpilot.document_agent import run_document_agent
from careerpilot.documents import TextDocument, chunk_document
from careerpilot.vector_store import SearchHit


@pytest.fixture
def inputs():
    doc = TextDocument('android', 'notes.txt', 'Use Room for offline storage.')
    retriever = Mock()
    retriever.retrieve.return_value = [SearchHit(chunk_document(doc)[0], 0.8)]
    generator = Mock(return_value=json.dumps({'status': 'answered', 'evidence': [
        {'source_id': 'S1', 'quote': doc.text}]}))
    return retriever, generator


def run(inputs, **changes):
    retriever, generator = inputs
    args = dict(question='How can I store Android data offline?', retrieval_service=retriever,
                owner_id='alice', document_ids=['android'], generator=generator)
    args.update(changes)
    return run_document_agent(None, **args)


def test_one_retrieval_one_generation_and_explicit_scope(inputs):
    result = run(inputs, document_ids=['android', 'android'], min_similarity=0.5)
    retriever, generator = inputs
    retriever.retrieve.assert_called_once_with('alice', 'How can I store Android data offline?',
        document_ids=['android'], top_k=4, min_similarity=0.5)
    generator.assert_called_once()
    assert result.status == 'answered'
    assert result.citations[0].document_id == 'android'


def test_empty_scope_does_not_load_model_or_connect(inputs):
    result = run(inputs, document_ids=[])
    assert result.reason == 'no_selected_documents'
    assert not result.model_called
    inputs[0].retrieve.assert_not_called()
    inputs[1].assert_not_called()


def test_no_hits_does_not_call_groq(inputs):
    inputs[0].retrieve.return_value = []
    result = run(inputs)
    assert result.reason == 'no_matching_passages'
    inputs[1].assert_not_called()


def test_model_abstention_is_not_replaced_by_general_knowledge(inputs):
    inputs[1].return_value = '{"status":"insufficient_evidence","evidence":[]}'
    result = run(inputs, question='What salary does this company offer?')
    assert result.status == 'insufficient_evidence'
    assert result.citations == ()
    inputs[1].assert_called_once()


def test_invalid_model_output_does_not_trigger_retry(inputs):
    inputs[1].return_value = '{"answer":"You are guaranteed a job"}'
    assert run(inputs).reason == 'invalid_model_response'
    inputs[1].assert_called_once()


def test_provider_and_database_failures_propagate(inputs):
    inputs[0].retrieve.side_effect = RuntimeError('database unavailable')
    with pytest.raises(RuntimeError, match='database unavailable'):
        run(inputs)
    inputs[1].assert_not_called()
    inputs[0].retrieve.side_effect = None
    inputs[1].side_effect = RuntimeError('provider unavailable')
    with pytest.raises(RuntimeError, match='provider unavailable'):
        run(inputs)


@pytest.mark.parametrize('changes', [
    pytest.param(dict(question=''), id='empty-question'),
    pytest.param(dict(question='x' * 2001), id='long-question'),
    pytest.param(dict(question='x\x00'), id='nul-question'),
    pytest.param(dict(owner_id=''), id='empty-owner'),
    pytest.param(dict(document_ids='android'), id='string-scope'),
    pytest.param(dict(document_ids=['']), id='empty-document-id'),
    pytest.param(dict(document_ids=['a'] * 101), id='too-many-documents'),
    pytest.param(dict(min_similarity=True), id='boolean-threshold'),
    pytest.param(dict(min_similarity=float('nan')), id='nan-threshold'),
    pytest.param(dict(min_similarity=2), id='out-of-range-threshold'),
])
def test_bad_requests_are_rejected_before_retrieval(inputs, changes):
    with pytest.raises(ValueError):
        run(inputs, **changes)
    inputs[0].retrieve.assert_not_called()
    inputs[1].assert_not_called()


def test_default_generator_is_wired_to_document_provider(inputs):
    with patch('careerpilot.document_agent.generate_evidence_selection', inputs[1]):
        result = run(inputs, generator=None)
    assert result.status == 'answered'
    inputs[1].assert_called_once()
