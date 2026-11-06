"""Explicit document-Q&A agent: one scoped retrieval and at most one LLM call.

The skill-comparison agent remains in agent.py. Document Q&A never reads or
writes profile memory, infers current skills, or executes document commands.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
import math
from numbers import Real
from typing import TYPE_CHECKING

from careerpilot.grounded_llm import generate_evidence_selection
from careerpilot.grounding import (DocumentAnswer, MAX_PASSAGES, abstain, evidence_prompt,
                                  prepare_evidence, validate_selection)

if TYPE_CHECKING:
    from careerpilot.config import Settings
    from careerpilot.retrieval import RetrievalService


def _identifier(value: str, limit: int) -> None:
    if not isinstance(value, str) or not value.strip() or '\x00' in value or len(value) > limit:
        raise ValueError('Provide a nonblank, bounded identifier without NUL characters.')


def run_document_agent(settings: Settings, question: str, *, retrieval_service: RetrievalService,
                       owner_id: str, document_ids: Sequence[str], min_similarity: float | None = None,
                       generator: Callable | None = None) -> DocumentAnswer:
    """Return exact quotations and citations, or abstain; no automatic retry.

    The caller selects the mode, owner and documents. IDs are application scope,
    not authentication. generator is a trusted dependency-injection seam for
    offline tests, not an option to expose to API clients.
    """
    if (not isinstance(question, str) or not question.strip() or '\x00' in question
            or len(question) > 2000):
        raise ValueError('Question must contain 1 to 2000 characters without NUL.')
    _identifier(owner_id, 128)
    if (not isinstance(document_ids, Sequence) or isinstance(document_ids, (str, bytes))
            or len(document_ids) > 100):
        raise ValueError('Select a sequence of at most 100 document IDs.')
    for document_id in document_ids:
        _identifier(document_id, 256)
    ids = tuple(dict.fromkeys(document_ids))
    if min_similarity is not None:
        if (isinstance(min_similarity, bool) or not isinstance(min_similarity, Real)
                or not -1 <= min_similarity <= 1 or not math.isfinite(min_similarity)):
            raise ValueError('min_similarity must be a finite number in [-1, 1].')
        min_similarity = float(min_similarity)
    if not ids:
        return abstain('no_selected_documents')
    hits = retrieval_service.retrieve(owner_id, question, document_ids=list(ids),
                                      top_k=MAX_PASSAGES, min_similarity=min_similarity)
    passages, truncated = prepare_evidence(hits, ids)
    if not passages:
        return abstain('no_matching_passages', context_truncated=truncated)
    generate = generator if generator is not None else generate_evidence_selection
    raw = generate(settings, evidence_prompt(question, passages))
    return validate_selection(raw, passages, context_truncated=truncated)
