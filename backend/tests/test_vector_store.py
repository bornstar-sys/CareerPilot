from dataclasses import replace
from unittest.mock import Mock

import pytest

from careerpilot.documents import TextDocument, chunk_document
from careerpilot.embeddings import EmbeddedChunk, EmbeddingVector
from careerpilot.retrieval import RetrievalService
from careerpilot.vector_store import PostgresVectorStore, EmbeddingSpaceMismatchError


VECTOR = EmbeddingVector((1.0,) + (0.0,) * 383, space_id='a' * 64)


def sample():
    document = TextDocument('role', 'role.txt', 'Kotlin Room REST')
    chunks = chunk_document(document, chunk_size=10, overlap=2)
    return document, [EmbeddedChunk(c, VECTOR) for c in chunks]


@pytest.fixture
def store():
    settings = Mock()
    settings.connect.side_effect = AssertionError('Invalid input must not reach the database.')
    return PostgresVectorStore(settings)


@pytest.mark.parametrize('values', [(), (0.0,) * 384, (2.0,) + (0.0,) * 383,
    (float('nan'),) + (0.0,) * 383, (float('inf'),) + (0.0,) * 383,
    (True,) + (0.0,) * 383, ('1',) + (0.0,) * 383, [1.0] + [0.0] * 383])
def test_invalid_vectors_do_not_reach_db(store, values):
    with pytest.raises(ValueError):
        store.search('owner', replace(VECTOR, values=values), document_ids=['role'])


@pytest.mark.parametrize('space_id', [None, '', 'not-a-fingerprint', 'Z' * 64])
def test_missing_or_invalid_fingerprint(store, space_id):
    with pytest.raises(ValueError):
        store.search('owner', replace(VECTOR, space_id=space_id), document_ids=['role'])


@pytest.mark.parametrize('changes', [dict(top_k=0), dict(top_k=True), dict(top_k=21),
    dict(min_similarity=float('nan')), dict(min_similarity=1.1), dict(min_similarity=True),
    dict(document_ids='role'), dict(document_ids=['']), dict(document_ids=['a'] * 101)])
def test_invalid_search_controls(store, changes):
    args = dict(document_ids=['role'])
    args.update(changes)
    with pytest.raises(ValueError):
        store.search('owner', VECTOR, **args)


def test_empty_scope_returns_nothing_without_connection(store):
    assert store.search('owner', VECTOR, document_ids=[]) == []


@pytest.mark.parametrize('owner', ['', ' ', 'a' * 129, 'bad\x00'])
def test_invalid_owner(store, owner):
    with pytest.raises(ValueError):
        store.list_documents(owner)


@pytest.mark.parametrize('mutation', ['missing', 'duplicate', 'reversed', 'source', 'text', 'offset', 'hash'])
def test_incomplete_or_forged_chunks_rejected(store, mutation):
    document, embedded = sample()
    if mutation == 'missing':
        embedded.pop()
    elif mutation == 'duplicate':
        embedded[1] = embedded[0]
    elif mutation == 'reversed':
        embedded.reverse()
    else:
        kwargs = {'source': dict(source_name='other.txt'), 'text': dict(text='forged'),
                  'offset': dict(start_char=1), 'hash': dict(content_sha256='f' * 64)}[mutation]
        embedded[0] = replace(embedded[0], chunk=replace(embedded[0].chunk, **kwargs))
    with pytest.raises(ValueError):
        store.replace_document('owner', document, embedded, chunk_size=10, overlap=2)


def test_mixed_embedding_spaces_rejected(store):
    document, embedded = sample()
    embedded[1] = replace(embedded[1], embedding=replace(VECTOR, space_id='b' * 64))
    with pytest.raises(EmbeddingSpaceMismatchError):
        store.replace_document('owner', document, embedded, chunk_size=10, overlap=2)


@pytest.mark.parametrize('text,size,overlap', [('x' * 1_048_577, 1000, 150),
    ('x' * 5001, 1, 0), ('x', True, 0), ('x', 10, 10)],
    ids=['oversized-utf8-document', 'too-many-chunk-windows',
         'boolean-chunk-size', 'overlap-equals-chunk-size'])
def test_resource_bounds_before_inference(text, size, overlap):
    store, embedder = Mock(), Mock()
    service = RetrievalService(store, embedder)
    with pytest.raises(ValueError):
        service.index_document('owner', TextDocument('id', 'name', text), chunk_size=size, overlap=overlap)
    embedder.embed_chunks.assert_not_called()
    store.replace_document.assert_not_called()


def test_indexing_batches_and_only_writes_after_all_embeddings():
    store, embedder = Mock(), Mock()
    calls = []
    def embed(chunks):
        calls.append(len(chunks))
        store.replace_document.assert_not_called()
        return [EmbeddedChunk(c, VECTOR) for c in chunks]
    embedder.embed_chunks.side_effect = embed
    store.replace_document.return_value = 300
    document = TextDocument('id', 'name', 'x' * 300)
    assert RetrievalService(store, embedder).index_document('owner', document, chunk_size=1, overlap=0) == 300
    assert calls == [256, 44]
    assert len(store.replace_document.call_args.args[2]) == 300


def test_embedding_failure_never_replaces_old_document():
    store, embedder = Mock(), Mock()
    embedder.embed_chunks.side_effect = [[], RuntimeError('model failed')]
    with pytest.raises(RuntimeError):
        RetrievalService(store, embedder).index_document(
            'owner', TextDocument('id', 'name', 'x' * 300), chunk_size=1, overlap=0)
    store.replace_document.assert_not_called()


def test_retrieve_passes_explicit_scope_and_controls():
    store, embedder = Mock(), Mock()
    embedder.embed_query.return_value = VECTOR
    store.search.return_value = ['result']
    result = RetrievalService(store, embedder).retrieve('alice', 'offline?', document_ids=['role'],
                                                       top_k=2, min_similarity=0.5)
    assert result == ['result']
    store.search.assert_called_once_with('alice', VECTOR, document_ids=['role'], top_k=2, min_similarity=0.5)
