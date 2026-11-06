"""Phase 4 document ingestion: local UTF-8 text and traceable character chunks.

No model calls, database writes, or profile updates occur in this module.
Offsets refer to normalized text (BOM removed; CRLF/CR converted to LF).
"""

from dataclasses import dataclass, field
from hashlib import sha256
import json
from pathlib import Path


def _nonblank(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonblank string.")


def _integer(value: int, name: str, minimum: int) -> None:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}.")


@dataclass(frozen=True)
class TextDocument:
    """An immutable document version with a caller-assigned logical identity.

    Reuse document_id when reloading the same source. Use a different ID for
    distinct sources, even if their filenames/text match. This is provenance,
    not a user authorization mechanism.
    """

    document_id: str
    source_name: str
    text: str
    content_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        _nonblank(self.document_id, "document_id")
        _nonblank(self.source_name, "source_name")
        _nonblank(self.text, "text")
        normalized = self.text.removeprefix("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
        _nonblank(normalized, "text")
        if "\x00" in normalized:
            raise ValueError("Text must not contain NUL characters.")
        object.__setattr__(self, "text", normalized)
        object.__setattr__(self, "content_sha256", sha256(normalized.encode("utf-8")).hexdigest())


@dataclass(frozen=True)
class DocumentChunk:
    """A text slice with zero-based, end-exclusive character offsets.

    index is zero-based. IDs identify document versions and positions;
    they do not establish that a source is accurate or trustworthy.
    """

    chunk_id: str
    document_id: str
    source_name: str
    content_sha256: str
    index: int
    start_char: int
    end_char: int
    text: str


def load_text_document(
    path: str | Path,
    *,
    document_id: str,
    max_bytes: int = 1_048_576,
) -> TextDocument:
    """Read one explicitly selected .txt/.md file, up to max_bytes.

    Only UTF-8 (optionally BOM-prefixed) is supported. Invalid/empty/oversized
    content raises ValueError; filesystem errors propagate to the caller.
    This local helper is not a sandbox for untrusted remote file paths.
    """
    _nonblank(document_id, "document_id")
    _integer(max_bytes, "max_bytes", 1)
    source = Path(path)
    if source.suffix.lower() not in {".txt", ".md"}:
        raise ValueError("Only .txt and .md files are supported.")
    with source.open("rb") as stream:
        raw = stream.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise ValueError(f"Document exceeds the {max_bytes}-byte limit.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError("Document must be UTF-8 encoded.") from None
    return TextDocument(document_id=document_id, source_name=source.name, text=text)


def chunk_document(
    document: TextDocument,
    *,
    chunk_size: int = 1000,
    overlap: int = 150,
) -> list[DocumentChunk]:
    """Split into fixed character windows, skipping whitespace-only windows.

    chunk_size is characters, not model tokens. Windows can split words.
    0 <= overlap < chunk_size guarantees progress and complete text coverage
    apart from whitespace-only windows. Text slices are never trimmed.
    """
    if not isinstance(document, TextDocument):
        raise TypeError("document must be a TextDocument.")
    _integer(chunk_size, "chunk_size", 1)
    _integer(overlap, "overlap", 0)
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size.")
    chunks: list[DocumentChunk] = []
    for start in range(0, len(document.text), chunk_size - overlap):
        end = min(start + chunk_size, len(document.text))
        text = document.text[start:end]
        if text.strip():
            identity = json.dumps(
                ["character-v1", document.document_id, document.content_sha256, start, end],
                ensure_ascii=False, separators=(",", ":"),
            )
            chunks.append(DocumentChunk(
                chunk_id=sha256(identity.encode("utf-8")).hexdigest(),
                document_id=document.document_id,
                source_name=document.source_name,
                content_sha256=document.content_sha256,
                index=len(chunks),
                start_char=start,
                end_char=end,
                text=text,
            ))
        if end == len(document.text):
            break
    return chunks
