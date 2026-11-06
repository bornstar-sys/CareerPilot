# Phase 4 — Step 3: vector storage and retrieval

This step adds persistent document indexing and scoped semantic retrieval.
Storage and retrieval have passed Windows checks. The explicit document-Q&A
agent and live cited-answer demo also passed; see phase4-grounded-answers.md.
This storage component does not change profile memory or call Groq.

## Prerequisites and installation

Keep the document and embedding files from Steps 1 and 2. PostgreSQL must be
running with the vector extension enabled in the public schema. The verified
local setup is PostgreSQL 17, pgvector 0.8.7, host 127.0.0.1, port 5433,
database/user careerpilot. Credentials remain in ignored infra/postgres/.env.

The installed optional dependencies are fastembed==0.9.1 and
psycopg[binary]==3.3.8. This patch does not change pyproject.toml or your lock/
requirements files. If reinstalling later, retain both in the rag extra.

Copy this archive's backend and docs folders into the repository root, merging
directories. Replace backend/src/careerpilot/embeddings.py with the included
version: its new model fingerprint is required by persistent storage. Other
files in this patch are additions. Do not replace your entire repository.

New Python modules:

- database.py: explicit local connection settings; no global environment changes.
- vector_store.py: schema setup, atomic replacement, listing, deletion and search.
- retrieval.py: bounded embedding batches followed by a database write.

## Verify in Windows PowerShell

Keep Docker Desktop running. From D:\Projects\CareerPilot\backend:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

This step added 66 offline tests and 11 optional database tests, reaching
253 passed and 200 subtests at its original checkpoint. With Step 4 installed,
the verified default suite is 317 passed, 11 skipped and 200 subtests passed.
Skips are deliberate until the database flag is enabled.
No model, database connection, or API key is needed for the offline tests.

Run the database tests explicitly:

```powershell
$env:CAREERPILOT_RUN_DB_TESTS = "1"
try {
    .\.venv\Scripts\python.exe -m pytest tests/test_vector_store_integration.py -q
}
finally {
    Remove-Item Env:\CAREERPILOT_RUN_DB_TESTS -ErrorAction SilentlyContinue
}
```

Expected: 11 passed. These tests create the schema if needed, use random test
owner IDs, and clean up only their documents. They retain the schema and a small
set of embedding-space metadata rows. They never drop a database or volume.
Use a development database, not a production connection.

Run the real-model demo twice in separate processes:

```powershell
.\.venv\Scripts\python.exe scripts/retrieval_demo.py
.\.venv\Scripts\python.exe scripts/retrieval_demo.py --query-only
```

Both should print check: PASS. The first stores two illustrative documents
under owner phase4-retrieval-demo, then searches them. The second reads the
existing vectors without reindexing documents. It still loads the model to
embed the new question. Expect the Android Room source first, two stored
documents/two chunks, and PASS for owner filtering, document filtering and
source offsets. Exact scores may differ across runtimes.

Rerunning the default demo replaces only its two named demo documents; it does
not append duplicate chunks. It intentionally retains them for query-only
checks. Use a different owner ID for your own files.

The demo uses your existing Windows cache under
%LOCALAPPDATA%\CareerPilot\models. It never downloads by default. If the cache
is missing, explicitly pass --allow-download. --cache-dir and --db-env allow
explicit alternate paths. Database tests accept CAREERPILOT_DB_ENV for an
alternate local settings file.

## Data and transaction behavior

initialize() creates schema careerpilot_rag and four tables: schema_meta,
embedding_spaces, documents, and chunks. It is safe to repeat for schema
version 1. An unsupported schema version raises an error; this is not a
general migration system. The existing vector extension must already exist.

A document is identified by (owner_id, document_id). Its chunks retain the
source name, normalized-content hash, stable chunk ID, chunk index, exact text
and zero-based, end-exclusive character offsets. Offsets refer to normalized
text from documents.py, not byte offsets or original CRLF file positions.

replace_document validates the complete ordered chunk set and embeddings
before connecting. The parent upsert, deletion of old chunks and insertion of
new chunks share one transaction. A failed write rolls back the entire
replacement. Concurrent replacements of the same document serialize on its
parent row; the last committed replacement wins. This is not optimistic
version conflict detection. Delete cascades to that document's chunks.

RetrievalService.index_document validates a 1 MiB normalized UTF-8 limit and
at most 5000 chunk windows before allocation/inference. Embedding calls use
batches of at most 256 chunks. All embeddings must succeed before replacement.
The token limit from Step 2 still applies: reduce chunk_size if a passage
exceeds the model token limit. Defaults remain 1000 characters and overlap 150.

## Embedding compatibility

EmbeddingVector now carries space_id. The real adapter hashes model/tokenizer
file bytes, model name, dimensions, preprocessing policy, query instruction,
CPU provider, and FastEmbed/ONNX Runtime/tokenizers versions. Paths and timestamps
are excluded. This is computed once when the local model loads.

The store refuses anonymous, nonfinite, non-unit or non-384-dimensional vectors.
It also rejects a selected document whose space differs from the query's space.
Equal dimensions alone do not establish compatible embeddings. A dependency,
model or policy change can require reindexing; this conservative behavior is
intentional. Reindex each selected document with the current embedder, then
retry. Do not bypass the check by editing stored fingerprints.

Deterministic test backends may explicitly provide a synthetic fingerprint.
Older fake backends remain compatible with embedding-only tests but their
anonymous vectors cannot enter persistent storage.

## Search scope and scores

Search requires owner_id and an explicit list of document IDs. It selects at
most 100 documents and returns top_k from 1 to 20 (default 5). Unknown or
out-of-scope IDs produce no rows; an empty scope returns an empty list. Owner
and document filters apply before ranking. Space checks and retrieval use one
repeatable-read snapshot, so a concurrent replacement cannot mix versions.

The first version uses exact cosine search: similarity = 1 - cosine distance.
Larger scores rank first; ties use document ID, chunk index, then chunk ID.
No approximate index is needed yet for the small local corpus. Scores are
similarities, not probabilities or confidence percentages. The optional
min_similarity threshold is in [-1, 1]; no threshold is assumed by default.
Even irrelevant sources can be returned as the nearest available match.
Relevance/abstention thresholds need Phase 5 evaluation.

IDs and text are bound SQL parameters. Table and operator names are fixed.
Owner scoping is application-level filtering, NOT authentication, authorization
or PostgreSQL row-level security. A future API must derive owner IDs from an
authenticated session. The current development database user has bootstrap
privileges; a limited application role belongs in deployment hardening.

## Validation scope

The 66 offline tests plus the earlier 50 document/embedding tests passed
in the preparation environment (Python 3.12). The user subsequently verified
the full Windows Python 3.13 suite and all 11 native PostgreSQL tests. The
Windows real-model indexing and separate query-only demos also passed.

The 11 SQL tests cover persistence across connections, ordering, scope,
replacement, rollback after a late constraint failure, incompatible embeddings,
deletion/cascade, empty scopes, deterministic ties, and Unicode/SQL-like text.
They are designed for the real Docker PostgreSQL setup. During preparation,
they also ran against embedded PostgreSQL/pgvector (PGlite) over a socket with
session-local prepared statements disabled in the scratch harness. That
single-backend harness is not native PostgreSQL 17 and does not validate
multi-connection concurrency, Docker volume durability, or Windows behavior.
No PGlite files or dependencies are included in this patch.

The real cached BGE model also passed the index-and-query demo, a separate
query-only process, and reindexing without duplicate chunks in that harness.
For the single illustrative offline-storage question, Android ranked first
(about 0.812 cosine similarity) above the web-styling passage (about 0.471).
This is a smoke test, not a retrieval-quality benchmark.

Source references for the storage primitives:

- https://www.psycopg.org/psycopg3/docs/basic/transactions.html
- https://www.psycopg.org/psycopg3/docs/basic/params.html
- https://github.com/pgvector/pgvector

## Grounded answers and evaluation

The explicit document-Q&A agent now consumes scoped retrieval results and
returns verified source quotations or an insufficient-evidence response. Its
offline and live demos passed on Windows. Retrieved text remains untrusted
evidence, never system instructions or verified profile skills. Phase 5 will
evaluate relevance, completeness, abstention and adversarial cases. See
progress.md for the completed implementation scope and Git closeout status.
