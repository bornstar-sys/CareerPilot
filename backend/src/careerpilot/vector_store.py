"""Transactional PostgreSQL/pgvector storage with explicit owner/document scope.

    The caller supplies the owner ID; authentication is a later phase. These
    filters are not a substitute for authentication or database row security.
"""

from collections.abc import Sequence
from dataclasses import dataclass
import json
import math
from numbers import Real
import re

from careerpilot.database import DatabaseSettings
from careerpilot.documents import DocumentChunk, TextDocument, chunk_document
from careerpilot.embeddings import EmbeddedChunk, EmbeddingVector, DIMENSIONS


class EmbeddingSpaceMismatchError(ValueError):
    """Re-embed selected documents with the query's model and preprocessing."""


@dataclass(frozen=True)
class SearchHit:
    chunk: DocumentChunk
    similarity: float


@dataclass(frozen=True)
class StoredDocument:
    document_id: str
    source_name: str
    content_sha256: str
    space_id: str
    chunk_count: int


SCHEMA_SQL = """
CREATE SCHEMA IF NOT EXISTS careerpilot_rag;
CREATE TABLE IF NOT EXISTS careerpilot_rag.schema_meta (
    singleton boolean PRIMARY KEY CHECK (singleton), version integer NOT NULL
);
INSERT INTO careerpilot_rag.schema_meta VALUES (true, 1) ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS careerpilot_rag.embedding_spaces (
    space_id text PRIMARY KEY CHECK (space_id ~ '^[0-9a-f]{64}$'),
    model_name text NOT NULL, policy text NOT NULL,
    dimensions integer NOT NULL CHECK (dimensions = 384)
);
CREATE TABLE IF NOT EXISTS careerpilot_rag.documents (
    owner_id text NOT NULL, document_id text NOT NULL,
    source_name text NOT NULL, content_sha256 text NOT NULL,
    space_id text NOT NULL REFERENCES careerpilot_rag.embedding_spaces(space_id),
    chunk_count integer NOT NULL CHECK (chunk_count > 0),
    chunk_size integer NOT NULL CHECK (chunk_size > 0),
    overlap integer NOT NULL CHECK (overlap >= 0 AND overlap < chunk_size),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (owner_id, document_id)
);
CREATE TABLE IF NOT EXISTS careerpilot_rag.chunks (
    owner_id text NOT NULL, document_id text NOT NULL, chunk_id text NOT NULL,
    chunk_index integer NOT NULL CHECK (chunk_index >= 0),
    start_char integer NOT NULL CHECK (start_char >= 0),
    end_char integer NOT NULL CHECK (end_char > start_char),
    content text NOT NULL CHECK (char_length(content) = end_char - start_char),
    embedding public.vector(384) NOT NULL,
    PRIMARY KEY (owner_id, document_id, chunk_id),
    UNIQUE (owner_id, document_id, chunk_index),
    FOREIGN KEY (owner_id, document_id)
        REFERENCES careerpilot_rag.documents(owner_id, document_id) ON DELETE CASCADE,
    CHECK (abs(1 + (embedding OPERATOR(public.<#>) embedding)) < 0.0001)
);
"""


def _label(value: str, name: str, limit: int = 256) -> None:
    if (not isinstance(value, str) or not value.strip() or "\x00" in value
            or len(value) > limit):
        raise ValueError(f"{name} must be a nonblank string of at most {limit} characters without NUL.")


def _vector(vector: EmbeddingVector) -> tuple[str, tuple]:
    if not isinstance(vector, EmbeddingVector):
        raise ValueError("Expected an EmbeddingVector.")
    if not isinstance(vector.space_id, str) or not re.fullmatch(r"[0-9a-f]{64}", vector.space_id):
        raise ValueError("A model fingerprint is required before storing or searching vectors.")
    _label(vector.model_name, "model_name")
    _label(vector.policy, "policy")
    if not isinstance(vector.values, tuple) or len(vector.values) != DIMENSIONS:
        raise ValueError("Vector must contain exactly 384 immutable values.")
    if any(isinstance(v, bool) or not isinstance(v, Real) for v in vector.values):
        raise ValueError("Vector values must be real numbers.")
    try:
        values = tuple(float(v) for v in vector.values)
    except (OverflowError, ValueError):
        raise ValueError("Vector values are out of range.") from None
    if not all(math.isfinite(v) for v in values) or not math.isclose(
        math.hypot(*values), 1, rel_tol=0, abs_tol=1e-5
    ):
        raise ValueError("Vector must be finite and normalized to unit length.")
    return json.dumps(values, allow_nan=False), (vector.space_id, vector.model_name, vector.policy, DIMENSIONS)


def prepare_document_chunks(document, *, chunk_size=1000, overlap=150):
    """Validate bounded indexing inputs before chunk allocation or inference."""
    if not isinstance(document, TextDocument):
        raise ValueError("Expected a TextDocument.")
    _label(document.document_id, "document_id")
    _label(document.source_name, "source_name", 1024)
    if len(document.text.encode("utf-8")) > 1_048_576:
        raise ValueError("Document exceeds the 1 MiB normalized UTF-8 limit.")
    # Bound memory and work even for an accidental one-character chunk size.
    if type(chunk_size) is not int or type(overlap) is not int or not 0 <= overlap < chunk_size:
        raise ValueError("Require integer chunk_size > overlap >= 0.")
    step = chunk_size - overlap
    windows = 1 + max(0, (len(document.text) - chunk_size + step - 1) // step)
    if windows > 5000:
        raise ValueError("Too many chunk windows; increase chunk_size or reduce overlap.")
    return chunk_document(document, chunk_size=chunk_size, overlap=overlap)


def _prepared_document(document, embedded, chunk_size, overlap):
    expected = prepare_document_chunks(document, chunk_size=chunk_size, overlap=overlap)
    if not isinstance(embedded, Sequence) or isinstance(embedded, (str, bytes)):
        raise ValueError("Embeddings must be a sequence.")
    if len(embedded) != len(expected):
        raise ValueError("Provide every chunk of the document exactly once, in order.")
    rows, identity = [], None
    for expected_chunk, item in zip(expected, embedded, strict=True):
        if not isinstance(item, EmbeddedChunk) or item.chunk != expected_chunk:
            raise ValueError("Chunk content or provenance does not match the source document.")
        literal, metadata = _vector(item.embedding)
        if identity is not None and metadata != identity:
            raise EmbeddingSpaceMismatchError("All document chunks must use one embedding space.")
        identity = metadata
        rows.append((item.chunk.chunk_id, item.chunk.index, item.chunk.start_char,
                     item.chunk.end_char, item.chunk.text, literal))
    return identity, rows


class PostgresVectorStore:
    def __init__(self, settings: DatabaseSettings):
        self.settings = settings

    def initialize(self) -> None:
        """Create only our schema/tables. Existing rows are retained."""
        with self.settings.connect() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(73501, 4)")
            extension = conn.execute(
                "SELECT n.nspname FROM pg_extension e JOIN pg_namespace n ON n.oid=e.extnamespace "
                "WHERE e.extname='vector'"
            ).fetchone()
            if extension != ("public",):
                raise RuntimeError("Enable the vector extension in the public schema first.")
            conn.execute(SCHEMA_SQL)
            version = conn.execute("SELECT version FROM careerpilot_rag.schema_meta WHERE singleton").fetchone()
            if version != (1,):
                raise RuntimeError("Unsupported RAG schema version; migration is required.")

    def replace_document(self, owner_id: str, document: TextDocument,
                         embedded: Sequence[EmbeddedChunk], *, chunk_size=1000, overlap=150) -> int:
        """Atomically insert/replace this owner's complete document version."""
        _label(owner_id, "owner_id", 128)
        identity, rows = _prepared_document(document, embedded, chunk_size, overlap)
        with self.settings.connect() as conn:
            conn.execute(
                "INSERT INTO careerpilot_rag.embedding_spaces VALUES (%s,%s,%s,%s) "
                "ON CONFLICT (space_id) DO NOTHING", identity,
            )
            registered = conn.execute(
                "SELECT space_id,model_name,policy,dimensions FROM careerpilot_rag.embedding_spaces "
                "WHERE space_id=%s", (identity[0],),
            ).fetchone()
            if registered != identity:
                raise EmbeddingSpaceMismatchError("Embedding-space metadata differs from the registered space.")
            # Upsert locks the parent row, serializing replacements of the same document.
            conn.execute(
                "INSERT INTO careerpilot_rag.documents "
                "(owner_id,document_id,source_name,content_sha256,space_id,chunk_count,chunk_size,overlap) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (owner_id,document_id) DO UPDATE SET "
                "source_name=EXCLUDED.source_name,content_sha256=EXCLUDED.content_sha256,"
                "space_id=EXCLUDED.space_id,chunk_count=EXCLUDED.chunk_count,"
                "chunk_size=EXCLUDED.chunk_size,overlap=EXCLUDED.overlap,updated_at=now()",
                (owner_id, document.document_id, document.source_name, document.content_sha256,
                 identity[0], len(rows), chunk_size, overlap),
            )
            conn.execute("DELETE FROM careerpilot_rag.chunks WHERE owner_id=%s AND document_id=%s",
                         (owner_id, document.document_id))
            with conn.cursor() as cursor:
                cursor.executemany(
                    "INSERT INTO careerpilot_rag.chunks "
                    "(owner_id,document_id,chunk_id,chunk_index,start_char,end_char,content,embedding) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s::public.vector)",
                    [(owner_id, document.document_id, *row) for row in rows],
                )
        return len(rows)

    def list_documents(self, owner_id: str) -> list[StoredDocument]:
        _label(owner_id, "owner_id", 128)
        with self.settings.connect() as conn:
            rows = conn.execute(
                "SELECT document_id,source_name,content_sha256,space_id,chunk_count "
                "FROM careerpilot_rag.documents WHERE owner_id=%s ORDER BY document_id", (owner_id,),
            ).fetchall()
        return [StoredDocument(*row) for row in rows]

    def delete_document(self, owner_id: str, document_id: str) -> bool:
        _label(owner_id, "owner_id", 128)
        _label(document_id, "document_id")
        with self.settings.connect() as conn:
            result = conn.execute("DELETE FROM careerpilot_rag.documents WHERE owner_id=%s AND document_id=%s",
                                  (owner_id, document_id))
            return result.rowcount > 0

    def search(self, owner_id: str, query: EmbeddingVector, *, document_ids: Sequence[str],
               top_k: int = 5, min_similarity: float | None = None) -> list[SearchHit]:
        """Exact cosine ranking within explicit scope. Scores are not confidence.

        Unknown/out-of-scope documents yield no rows. Incompatible selected
        documents raise an error instead of silently searching across spaces.
        No default relevance cutoff is assumed; an empty filtered result is valid.
        """
        _label(owner_id, "owner_id", 128)
        literal, identity = _vector(query)
        if not isinstance(document_ids, Sequence) or isinstance(document_ids, (str, bytes)):
            raise ValueError("document_ids must be a sequence.")
        if len(document_ids) > 100:
            raise ValueError("Select at most 100 documents per search.")
        for document_id in document_ids:
            _label(document_id, "document_id")
        ids = list(dict.fromkeys(document_ids))
        if type(top_k) is not int or not 1 <= top_k <= 20:
            raise ValueError("top_k must be an integer from 1 to 20.")
        if min_similarity is not None:
            if (isinstance(min_similarity, bool) or not isinstance(min_similarity, Real)
                    or not -1 <= min_similarity <= 1 or not math.isfinite(min_similarity)):
                raise ValueError("min_similarity must be a finite number from -1 to 1.")
            min_similarity = float(min_similarity)
        if not ids:
            return []
        with self.settings.connect() as conn:
            # Space checks and retrieval observe the same snapshot during replacement.
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            selected = conn.execute(
                "SELECT space_id FROM careerpilot_rag.documents WHERE owner_id=%s AND document_id=ANY(%s)",
                (owner_id, ids),
            ).fetchall()
            if not selected:
                return []
            if any(row[0] != identity[0] for row in selected):
                raise EmbeddingSpaceMismatchError("Selected documents require re-embedding with the query's model.")
            registered = conn.execute(
                "SELECT space_id,model_name,policy,dimensions FROM careerpilot_rag.embedding_spaces WHERE space_id=%s",
                (identity[0],),
            ).fetchone()
            if registered != identity:
                raise EmbeddingSpaceMismatchError("Query metadata does not match the stored embedding space.")
            rows = conn.execute(
                "WITH candidates AS (SELECT c.document_id,d.source_name,d.content_sha256,"
                "c.chunk_id,c.chunk_index,c.start_char,c.end_char,c.content,"
                "1 - (c.embedding OPERATOR(public.<=>) %s::public.vector) AS similarity "
                "FROM careerpilot_rag.chunks c JOIN careerpilot_rag.documents d "
                "ON c.owner_id=d.owner_id AND c.document_id=d.document_id "
                "WHERE c.owner_id=%s AND c.document_id=ANY(%s) AND d.space_id=%s) "
                "SELECT * FROM candidates WHERE (%s::double precision IS NULL OR similarity >= %s) "
                "ORDER BY similarity DESC,document_id,chunk_index,chunk_id LIMIT %s",
                (literal, owner_id, ids, identity[0], min_similarity, min_similarity, top_k),
            ).fetchall()
        return [SearchHit(DocumentChunk(
            chunk_id=row[3], document_id=row[0], source_name=row[1], content_sha256=row[2],
            index=row[4], start_char=row[5], end_char=row[6], text=row[7],
        ), similarity=max(-1.0, min(1.0, float(row[8])))) for row in rows]
