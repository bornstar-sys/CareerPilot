"""Bounded local BGE embeddings, with source metadata preserved.

Importing this module never imports FastEmbed or loads/downloads a model.
The optional rag dependencies are needed only for real embedding calls.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from hashlib import file_digest, sha256
from importlib.metadata import version
from itertools import islice
import json
import math
from numbers import Real
import os
from pathlib import Path
from typing import Protocol

from careerpilot.documents import DocumentChunk


MODEL_NAME = "BAAI/bge-small-en-v1.5"
DIMENSIONS = 384
MAX_INPUT_CHARS = 20_000
MAX_CHUNKS_PER_CALL = 256
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
EMBEDDING_POLICY = "bge-query-instruction-l2-v1"


class EmbeddingError(RuntimeError):
    """A model loading or output validation failure."""


class TextTooLongError(ValueError):
    """Text must be split into smaller chunks or the query shortened."""


@dataclass(frozen=True)
class EmbeddingVector:
    """Normalized values plus the model and preprocessing policy used."""

    values: tuple[float, ...]
    model_name: str = MODEL_NAME
    policy: str = EMBEDDING_POLICY
    # None is allowed for older/test backends, but such vectors cannot be stored.
    space_id: str | None = None


@dataclass(frozen=True)
class EmbeddedChunk:
    chunk: DocumentChunk
    embedding: EmbeddingVector


class EmbeddingBackend(Protocol):
    """Small adapter boundary for deterministic tests without model downloads."""

    max_tokens: int

    def count_tokens(self, text: str) -> int: ...

    def embed(self, texts: list[str]) -> Iterable[Sequence[float]]: ...


def default_model_cache() -> Path:
    """Reuse the Windows smoke-test cache; use a home cache elsewhere."""
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "CareerPilot" / "models"
    return Path.home() / ".cache" / "careerpilot" / "models"


class _FastEmbedBackend:
    """FastEmbed 0.9.1 adapter; tokenizer internals are isolated here.

    FastEmbed.token_count counts after truncation in this version. A cloned
    tokenizer with truncation and padding disabled gives the full length.
    The inference tokenizer itself is never changed.
    """

    def __init__(self, cache_dir: Path, local_files_only: bool):
        from fastembed import TextEmbedding

        self._model = TextEmbedding(
            model_name=MODEL_NAME,
            cache_dir=str(cache_dir),
            providers=["CPUExecutionProvider"],
            threads=2,
            local_files_only=local_files_only,
        )
        if self._model.embedding_size != DIMENSIONS:
            raise EmbeddingError("Unexpected embedding model dimensions.")
        tokenizer = self._model.model.tokenizer
        truncation = tokenizer.truncation
        configured_limit = truncation["max_length"] if truncation else 512
        if type(configured_limit) is not int or configured_limit < 1:
            raise EmbeddingError("Unexpected tokenizer limit.")
        self.max_tokens = min(configured_limit, 512)
        self._counter = type(tokenizer).from_str(tokenizer.to_str())
        self._counter.no_truncation()
        self._counter.no_padding()
        self.space_id = fingerprint_model(self._model.model._model_dir)

    def count_tokens(self, text: str) -> int:
        return len(self._counter.encode(text, add_special_tokens=True).ids)

    def embed(self, texts: list[str]) -> Iterable[Sequence[float]]:
        # Query preparation happens in LocalEmbedder, exactly once.
        return self._model.embed(texts, batch_size=16, parallel=None)


def fingerprint_model(model_dir: str | Path) -> str:
    """Hash model/tokenizer bytes and the runtime/preprocessing identity once.

    Paths and modification times are excluded, so copied caches have the same
    identity. Optional absent tokenizer files have an explicit null marker.
    """
    root = Path(model_dir)
    files = {}
    for name in ("model_optimized.onnx", "tokenizer.json", "tokenizer_config.json",
                 "config.json", "special_tokens_map.json"):
        path = root / name
        if not path.is_file():
            if name in {"model_optimized.onnx", "tokenizer.json", "tokenizer_config.json"}:
                raise EmbeddingError("Required model fingerprint file is missing.")
            files[name] = None
        else:
            with path.open("rb") as stream:
                files[name] = file_digest(stream, "sha256").hexdigest()
    identity = {
        "format": "careerpilot-embedding-space-v1", "files": files,
        "model": MODEL_NAME, "dimensions": DIMENSIONS, "policy": EMBEDDING_POLICY,
        "query_prefix": QUERY_PREFIX, "provider": "CPUExecutionProvider",
        "runtime": {name: version(name) for name in ("fastembed", "onnxruntime", "tokenizers")},
    }
    return sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _validate_text(text: str) -> None:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Embedding text must be a nonblank string.")
    if len(text) > MAX_INPUT_CHARS:
        raise TextTooLongError("Text exceeds the character limit; split or shorten it.")
    if "\x00" in text:
        raise ValueError("Embedding text must not contain NUL characters.")


def _normalized_vector(raw: Sequence[float]) -> EmbeddingVector:
    try:
        values = tuple(islice(iter(raw), DIMENSIONS + 1))
    except TypeError:
        raise EmbeddingError("Embedding output is not a vector.") from None
    if len(values) != DIMENSIONS:
        raise EmbeddingError("Embedding output must have 384 dimensions.")
    if any(isinstance(v, bool) or not isinstance(v, Real) for v in values):
        raise EmbeddingError("Embedding values must be real numbers.")
    try:
        floats = tuple(float(v) for v in values)
    except (ValueError, OverflowError):
        raise EmbeddingError("Embedding values are out of range.") from None
    if not all(math.isfinite(v) for v in floats):
        raise EmbeddingError("Embedding values must be finite.")
    norm = math.hypot(*floats)
    if not math.isfinite(norm) or norm == 0:
        raise EmbeddingError("Embedding vector must have a finite, nonzero norm.")
    return EmbeddingVector(values=tuple(v / norm for v in floats))


class LocalEmbedder:
    """Reuse one CPU model for chunks and queries; cached files only by default.

    Set local_files_only=False explicitly to permit a model download. A supplied
    backend is for tests and must obey EmbeddingBackend's contract. This class
    is intended for sequential use in the current command-line backend.
    """

    def __init__(
        self,
        *,
        cache_dir: str | Path | None = None,
        local_files_only: bool = True,
        backend: EmbeddingBackend | None = None,
    ):
        if type(local_files_only) is not bool:
            raise ValueError("local_files_only must be a boolean.")
        self._cache_dir = Path(cache_dir) if cache_dir is not None else default_model_cache()
        self._local_files_only = local_files_only
        self._backend = backend

    def _get_backend(self) -> EmbeddingBackend:
        if self._backend is None:
            try:
                self._backend = _FastEmbedBackend(self._cache_dir, self._local_files_only)
            except ImportError:
                raise EmbeddingError(
                    'Embedding dependencies are unavailable. Install the project with .[rag].'
                ) from None
            except Exception:
                raise EmbeddingError(
                    "Could not load the embedding model. Check the rag dependencies and "
                    "cache; if the model is missing, run the demo with --allow-download."
                ) from None
        return self._backend

    def _embed_texts(self, texts: list[str]) -> list[EmbeddingVector]:
        backend = self._get_backend()
        if type(backend.max_tokens) is not int or backend.max_tokens < 1:
            raise EmbeddingError("Invalid backend token limit.")
        # Check every input before any inference, including special/query tokens.
        for index, text in enumerate(texts):
            try:
                count = backend.count_tokens(text)
            except Exception:
                raise EmbeddingError("Could not count embedding input tokens.") from None
            if type(count) is not int or count < 1:
                raise EmbeddingError("Invalid backend token count.")
            if count > backend.max_tokens:
                raise TextTooLongError(
                    f"Input {index} has {count} tokens; the limit is {backend.max_tokens}. "
                    "Split the document into smaller chunks or shorten the query."
                )
        try:
            # One extra result detects a mismatch without consuming an unbounded stream.
            rows = list(islice(backend.embed(texts), len(texts) + 1))
        except Exception:
            raise EmbeddingError("Embedding inference failed; no results were returned.") from None
        if len(rows) != len(texts):
            raise EmbeddingError("Embedding output count does not match the input count.")
        space_id = getattr(backend, "space_id", None)
        return [replace(_normalized_vector(row), space_id=space_id) for row in rows]

    def embed_chunks(self, chunks: Sequence[DocumentChunk]) -> list[EmbeddedChunk]:
        if not isinstance(chunks, Sequence) or isinstance(chunks, (str, bytes)):
            raise ValueError("chunks must be a sequence of DocumentChunk objects.")
        if len(chunks) > MAX_CHUNKS_PER_CALL:
            raise ValueError("Embed at most 256 chunks per call; use smaller batches.")
        snapshot = tuple(chunks)
        if not snapshot:
            return []
        seen: set[str] = set()
        for chunk in snapshot:
            if not isinstance(chunk, DocumentChunk):
                raise ValueError("Each item must be a DocumentChunk.")
            if chunk.chunk_id in seen:
                raise ValueError("Duplicate chunk IDs are not allowed in one batch.")
            seen.add(chunk.chunk_id)
            _validate_text(chunk.text)
        vectors = self._embed_texts([chunk.text for chunk in snapshot])
        return [EmbeddedChunk(chunk, vector) for chunk, vector in zip(snapshot, vectors, strict=True)]

    def embed_query(self, query: str) -> EmbeddingVector:
        _validate_text(query)
        # BGE's recommended short-query instruction; passages remain unchanged.
        prepared = QUERY_PREFIX + query
        return self._embed_texts([prepared])[0]
