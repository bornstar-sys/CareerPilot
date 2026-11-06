# ADR 0006: local document RAG with cited extractive answers

Date: 2026-11-06
Status: Accepted for the Phase 4 local CLI implementation

## Context

CareerPilot already compares explicit skills and optionally reads a saved
SQLite profile. Phase 4 needs document evidence that can be persisted,
retrieved for a selected owner/document scope, and traced back to source text.
The existing free-tier Groq setup is retained for generation. The user chose
PostgreSQL with pgvector after considering MySQL.

## Decisions

1. Ingest explicit UTF-8 .txt/.md sources, normalize line endings/BOM, and
   identify versions with content hashes. Use deterministic overlapping
   character chunks with normalized, end-exclusive source offsets.
2. Embed locally using FastEmbed 0.9.1 and BAAI/bge-small-en-v1.5 on CPU. Store
   finite unit vectors of 384 dimensions. Count full prepared tokens before
   inference; reject oversized inputs rather than silently truncate them.
3. Hash model/tokenizer artifacts, preprocessing and relevant runtime versions
   into an embedding-space identity. Reject incompatible document/query spaces;
   require reindexing when the identity changes.
4. Store documents/chunks in PostgreSQL 17 with pgvector 0.8.7, using the pinned
   local Docker image tag and localhost port 5433. The image is not digest-pinned.
   Keep profile memory in SQLite and database credentials in an ignored file.
5. Replace complete documents atomically in one transaction. Scope all document
   operations by owner ID, and searches by explicit document IDs. Use exact
   cosine ranking for the small corpus, with no universal relevance cutoff.
6. Add an explicit document-Q&A agent alongside the skill-comparison agent.
   Retrieve once, make at most one Groq call, and give that path no tools or
   profile writes. The model receives bounded passage/question data separately
   from system instructions.
7. Have the model select exact source quotations. Validate the JSON structure,
   source labels and quote membership, then derive citation metadata and offsets
   in application code. Render only verified excerpts. Reject the whole answer
   when any citation is invalid; do not retry or repair automatically.
8. Return an insufficient-evidence result for empty/no-hit scopes, model
   abstention, or invalid evidence selection, with distinct reasons. Propagate
   infrastructure failures; do not report a connection failure as missing evidence.

## Alternatives and consequences

MySQL was considered; PostgreSQL/pgvector matches the selected stack and the
required vector operations. An approximate index is deferred until corpus
size and measured performance justify it. External embedding APIs are not
needed for this local model path.

Extractive answers give deterministic quote/provenance checks. They do not
provide general synthesized recommendations, and valid quotes can still be
irrelevant, incomplete or misleading. Phase 5 must evaluate relevance,
abstention, conflicting sources and adversarial passages before widening the
answer format. Prompt instructions alone do not guarantee semantic grounding.

Owner filters are not authentication. The bootstrap database account is for
local development. Production access control, database roles, backups and
deployment validation remain later work. Source text is untrusted; future
interfaces must escape it rather than render it as executable markup.

## Evidence

The user verified 317 tests and 200 subtests on Windows, plus 11 native
PostgreSQL integration tests separately. Real embedding/retrieval demos,
separate-process persistence, and offline/live grounded-answer demos passed.
The live scenario produced a Room quotation with source offsets, abstained on
an unsupported salary question, and made no model call for an empty scope.
These are checkpoint smoke checks, not a benchmark of all possible questions.

See [progress](../progress.md), [storage](../phase4-vector-store.md), and
[document answers](../phase4-grounded-answers.md) for contracts and validation.
