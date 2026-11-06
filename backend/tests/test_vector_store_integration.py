"""Opt-in tests against the local development database; no model downloads.

Each test uses random owner IDs and deletes only documents belonging to those
IDs. No schema, volume, database, or unrelated user's data is dropped.
"""
from dataclasses import replace
from hashlib import sha256
import os
from pathlib import Path
from uuid import uuid4

import pytest

from careerpilot.database import load_database_settings
from careerpilot.documents import TextDocument, chunk_document
from careerpilot.embeddings import EmbeddedChunk, EmbeddingVector
from careerpilot.vector_store import EmbeddingSpaceMismatchError, PostgresVectorStore
from careerpilot import vector_store as module


pytestmark = pytest.mark.skipif(os.environ.get('CAREERPILOT_RUN_DB_TESTS') != '1',
                              reason='Set CAREERPILOT_RUN_DB_TESTS=1 for local PostgreSQL tests.')
SPACE = sha256(b'careerpilot-synthetic-integration-v1').hexdigest()


def vector(index=0, sign=1.0, space=SPACE):
    values = [0.0] * 384
    values[index] = sign
    return EmbeddingVector(tuple(values), model_name='test-basis', policy='test-unit-v1', space_id=space)


@pytest.fixture
def db():
    default = Path(__file__).resolve().parents[2] / 'infra/postgres/.env'
    # tests is backend/tests; parents[2] is the repository root.
    settings = load_database_settings(os.environ.get('CAREERPILOT_DB_ENV', str(default)))
    store = PostgresVectorStore(settings)
    store.initialize()
    owners = ['test-' + uuid4().hex for _ in range(2)]
    try:
        yield store, owners
    finally:
        with settings.connect() as conn:
            conn.execute('DELETE FROM careerpilot_rag.documents WHERE owner_id=ANY(%s)', (owners,))


def put(store, owner, doc_id='role', text='Kotlin Room REST', values=None, size=10, overlap=2):
    doc = TextDocument(doc_id, doc_id + '.txt', text)
    chunks = chunk_document(doc, chunk_size=size, overlap=overlap)
    vectors = values or [vector()] * len(chunks)
    store.replace_document(owner, doc, [EmbeddedChunk(c, v) for c, v in zip(chunks, vectors, strict=True)],
                           chunk_size=size, overlap=overlap)
    return doc, chunks


def test_persists_across_connections_and_initialization(db):
    store, (owner, _) = db
    doc, chunks = put(store, owner)
    reopened = PostgresVectorStore(store.settings)
    reopened.initialize()
    listed = reopened.list_documents(owner)
    assert len(listed) == 1
    assert listed[0].content_sha256 == doc.content_sha256
    assert listed[0].chunk_count == len(chunks)
    hits = reopened.search(owner, vector(), document_ids=['role'])
    assert [h.chunk for h in hits] == chunks
    assert all(abs(h.similarity - 1) < 1e-6 for h in hits)


def test_cosine_order_top_k_and_threshold(db):
    store, (owner, _) = db
    put(store, owner, text='abcdefghijklmno', size=5, overlap=0,
        values=[vector(0, -1), vector(1), vector(0)])
    hits = store.search(owner, vector(), document_ids=['role'])
    assert [h.chunk.index for h in hits] == [2, 1, 0]
    assert [h.similarity for h in hits] == [1, 0, -1]
    assert len(store.search(owner, vector(), document_ids=['role'], top_k=2)) == 2
    assert len(store.search(owner, vector(), document_ids=['role'], min_similarity=0.5)) == 1
    assert store.search(owner, vector(2), document_ids=['role'], min_similarity=0.5) == []


def test_owner_and_document_filters_apply_before_ranking(db):
    store, (alice, bob) = db
    put(store, alice, 'shared', 'alice content', size=100, overlap=0, values=[vector(1)])
    put(store, alice, 'other', 'unselected content', size=100, overlap=0)
    put(store, bob, 'shared', 'bob private content', size=100, overlap=0)
    result = store.search(alice, vector(), document_ids=['shared'])
    assert len(result) == 1
    assert result[0].chunk.text == 'alice content'
    assert result[0].similarity == 0
    assert [d.document_id for d in store.list_documents(bob)] == ['shared']
    assert store.delete_document(bob, 'other') is False
    assert store.search(bob, vector(), document_ids=['other']) == []


def test_reindex_is_idempotent_and_replacement_removes_stale_chunks(db):
    store, (owner, _) = db
    put(store, owner)
    put(store, owner)
    assert len(store.search(owner, vector(), document_ids=['role'])) == 2
    doc, chunks = put(store, owner, text='new', size=10, overlap=2)
    assert [h.chunk for h in store.search(owner, vector(), document_ids=['role'])] == chunks
    assert store.list_documents(owner)[0].content_sha256 == doc.content_sha256
    assert store.list_documents(owner)[0].chunk_count == 1


def test_failed_insert_rolls_back_document_and_chunks(db, monkeypatch):
    import psycopg
    store, (owner, _) = db
    _, original = put(store, owner)
    before = store.list_documents(owner)
    original_prepare = module._prepared_document
    def corrupt_after_validation(*args):
        identity, rows = original_prepare(*args)
        # Force a database constraint failure AFTER parent upsert and old-chunk deletion.
        rows[-1] = (*rows[-1][:4], 'wrong length', rows[-1][5])
        return identity, rows
    monkeypatch.setattr(module, '_prepared_document', corrupt_after_validation)
    with pytest.raises(psycopg.errors.CheckViolation):
        put(store, owner, text='brand new text')
    assert store.list_documents(owner) == before
    assert [h.chunk for h in store.search(owner, vector(), document_ids=['role'])] == original


def test_incompatible_space_requires_reembedding(db):
    store, (owner, _) = db
    put(store, owner)
    other = vector(space=sha256(b'other-test-space').hexdigest())
    with pytest.raises(EmbeddingSpaceMismatchError):
        store.search(owner, other, document_ids=['role'])
    put(store, owner, values=[other, other])
    assert len(store.search(owner, other, document_ids=['role'])) == 2
    with pytest.raises(EmbeddingSpaceMismatchError):
        store.search(owner, vector(), document_ids=['role'])


def test_same_fingerprint_cannot_claim_different_metadata(db):
    store, (owner, _) = db
    put(store, owner)
    bad = replace(vector(), policy='different-policy')
    with pytest.raises(EmbeddingSpaceMismatchError):
        store.search(owner, bad, document_ids=['role'])
    with pytest.raises(EmbeddingSpaceMismatchError):
        put(store, owner, values=[bad, bad])
    assert len(store.search(owner, vector(), document_ids=['role'])) == 2


def test_delete_cascades_and_keeps_other_owner(db):
    store, (owner, other) = db
    put(store, owner)
    put(store, other)
    assert store.delete_document(owner, 'role') is True
    assert store.delete_document(owner, 'role') is False
    assert store.list_documents(owner) == []
    with store.settings.connect() as conn:
        assert conn.execute('SELECT count(*) FROM careerpilot_rag.chunks WHERE owner_id=%s',
                            (owner,)).fetchone() == (0,)
    assert len(store.search(other, vector(), document_ids=['role'])) == 2


def test_empty_unknown_and_duplicate_scopes(db):
    store, (owner, _) = db
    assert store.search(owner, vector(), document_ids=['missing']) == []
    put(store, owner)
    assert store.search(owner, vector(), document_ids=[]) == []
    assert len(store.search(owner, vector(), document_ids=['role', 'role', 'missing'])) == 2


def test_bound_parameters_preserve_sql_like_and_unicode_text(db):
    store, (owner, _) = db
    doc_id = "x'); DROP TABLE careerpilot_rag.documents; --"
    text = "It's Kotlin; हिन्दी 🙂\nRoom supports offline data."
    _, chunks = put(store, owner, doc_id=doc_id, text=text, size=100, overlap=0)
    assert store.search(owner, vector(), document_ids=[doc_id])[0].chunk == chunks[0]
    assert len(store.list_documents(owner)) == 1


def test_ties_are_stable_by_document_then_chunk(db):
    store, (owner, _) = db
    put(store, owner, 'z')
    put(store, owner, 'a')
    hits = store.search(owner, vector(), document_ids=['z', 'a'])
    assert [(h.chunk.document_id, h.chunk.index) for h in hits] == [('a', 0), ('a', 1), ('z', 0), ('z', 1)]
