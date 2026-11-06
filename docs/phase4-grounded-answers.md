# Phase 4 — Step 4: cited document answers

Status: the 64 new tests, the 317-test Windows suite and both offline and live
demos passed. The live demo explicitly loads backend/.env. The Phase 4 local
CLI implementation is verified; Git commit/push remains a separate checkpoint.

## Verified starting point

The Windows checkpoint before this patch is:

- 253 passed, 11 intentionally skipped database tests, 200 subtests passed.
- The 11 PostgreSQL integration tests passed when explicitly enabled.
- The real embedding/index-and-query demo passed.
- A separate query-only process retrieved the existing two documents/chunks.
- Owner/document filtering and exact source offsets passed.

This package adds three modules, three test files, one demo and this document.
All files are additions. It does not replace agent.py, planner.py, llm.py,
memory.py, configuration, dependencies or your existing Step 3 files.

## Scope and design

The new public entry point is careerpilot.document_agent.run_document_agent.
It is an explicit document-Q&A mode alongside careerpilot.agent.run_agent,
which continues to handle verified skill comparison and profile memory.
The caller selects the mode; there is no model-driven mode switch in this step.

The document agent performs one scoped retrieval and at most one generation
call. The LLM selects short exact quotations. The application verifies every
quotation against the retrieved passage, derives its source details/offsets,
and renders the cited excerpts. This is an extractive answer format.

The entry point never accesses profile memory, writes to the database, infers
current skills, executes tools, runs code from documents, or searches the web.
A document's claim about the user's skills cannot become a saved profile fact.

## Apply and verify

Merge the archive's backend and docs folders into D:\Projects\CareerPilot.
Keep the corrected test_vector_store.py from Step 3; it is not in this patch.
No dependency installation or Docker/schema changes are needed.

From D:\Projects\CareerPilot\backend:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_grounding.py tests/test_document_agent.py tests/test_grounded_llm.py -q
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/grounded_answer_demo.py
```

Expected new tests: 64 passed. With the previous baseline unchanged, the full
suite should show 317 passed, 11 skipped, 200 subtests passed. Database tests
remain opt-in under CAREERPILOT_RUN_DB_TESTS. New tests use short explicit IDs
for large string fixtures to avoid the Windows environment-variable limit.

The default demo prints check: PASS and mode: offline-scripted-fixtures. It
uses a scripted retriever/generator to exercise success, abstention and an
empty scope. It makes no network requests and needs no database, model or key.
Its model_called field records whether the generation adapter was invoked;
in offline mode that adapter is a scripted fixture, not Groq.

Then keep Docker Desktop running and use the live mode:

```powershell
.\.venv\Scripts\python.exe scripts/grounded_answer_demo.py --live
```

Live mode explicitly passes backend/.env to load_settings(), resolving that
path from the demo script's location. The loader otherwise defaults to mock
unless process environment variables select a provider. Do not paste the key into a terminal
command, chat or source file. It reads the two already-indexed Step 3 demo
documents under owner phase4-retrieval-demo, embeds each question with the
cached local model, and makes two Groq calls. The empty-scope check makes none.
The live demo sends the questions and selected passage text to Groq, as RAG
context. It sends no owner IDs, filenames, document IDs, or profile records.

Expected live results:

| Check | Expected |
| --- | --- |
| Question about offline Android storage | answered, with a Room quotation and citation |
| Question about a guaranteed annual salary | insufficient_evidence, reason model_insufficient_evidence |
| Empty document selection | insufficient_evidence, model_called false |
| Overall check | PASS |

The model's exact quote selection may vary. If a check fails, preserve the
printed output and investigate; do not relax citation validation to force PASS.
No API calls were made with your credentials during patch preparation.

If the Step 3 sources are missing, run scripts/retrieval_demo.py first. The
live grounded demo reads existing records and never initializes or indexes the
database. --db-env and --cache-dir allow explicit alternate paths. Model
downloads remain disabled. An embedding-space mismatch means the documents
must be reindexed with the current local model/runtime.

## API example

```python
from pathlib import Path
from careerpilot.config import load_settings
from careerpilot.database import load_database_settings
from careerpilot.document_agent import run_document_agent
from careerpilot.embeddings import LocalEmbedder
from careerpilot.retrieval import RetrievalService
from careerpilot.vector_store import PostgresVectorStore

# This example is run from the backend directory.
settings = load_settings(env_file=Path('.env'))
store = PostgresVectorStore(load_database_settings('../infra/postgres/.env'))
retrieval = RetrievalService(store, LocalEmbedder())
result = run_document_agent(
    settings,
    'How can I store Android application data offline?',
    retrieval_service=retrieval,
    owner_id='phase4-retrieval-demo',
    document_ids=['demo-android-storage'],
)
print(result.answer)
for citation in result.citations:
    print(citation.source_id, citation.source_name,
          citation.start_char, citation.end_char)
```

Owner IDs remain caller-supplied application scope, not authentication. A
future authenticated API must derive the owner from its session and validate
access to the chosen documents. The generator injection argument is only for
trusted tests/application code; do not expose it as a remote API parameter.

## Contract and bounds

- Questions: 1–2000 characters; IDs retain Step 3 limits, at most 100 selected
  documents. Empty document selection returns immediately.
- Retrieval: top four scoped cosine hits, once. min_similarity is optional and
  defaults to None. There is no claimed universal relevance threshold.
- Context: at most 2000 characters per passage, 6000 total; prefixes are used
  when necessary. context_truncated reports any truncation. Duplicate hits
  are removed and inconsistent/out-of-scope retriever output raises an error.
- Generation: one Groq request, JSON-object mode, 2048 maximum completion
  tokens, existing configured timeout, no SDK retries. GPT-OSS uses low
  reasoning effort. Instructions are a system message; passage/question data
  are a separate JSON user message. No tools are supplied.
- Selection: 1–4 quotations, each at most 600 characters. Model output is
  limited to 12000 characters before JSON parsing. Extra keys, duplicate keys,
  unknown labels, malformed JSON, nonstandard constants and altered quotes
  are rejected. Any bad citation rejects the entire answer.
- Answer: a fixed introduction followed by exact source quotes and labels.
  The model cannot add uncited free-form claims or source metadata.

Each Citation contains source_id (request-local S1 etc.), document_id,
source_name, content_sha256, chunk_id, quote, similarity and absolute quote
start_char/end_char. Offsets are zero-based/end-exclusive in the normalized
source document. They identify the quoted substring, not the whole chunk.
If the same quote repeats in a passage, its first occurrence is used. The hash
identifies the document version; citation offsets may differ after reindexing.

The answer is plain text. Future UI code must escape document text, quotes and
source names; never interpret them as HTML, commands or trusted instructions.

## Failure and abstention behavior

| Situation | Result |
| --- | --- |
| Empty selected scope | insufficient_evidence / no_selected_documents; no model call |
| No retrieved passages | insufficient_evidence / no_matching_passages; no model call |
| Model says evidence is insufficient | insufficient_evidence / model_insufficient_evidence |
| Malformed JSON or invalid quote/citation | insufficient_evidence / invalid_model_response; no repair retry |
| Database, embedding or retrieval contract error | Error propagates to caller |
| Groq rejects, times out or returns incomplete output | Safe DocumentLLMError; no automatic retry |

Failures of infrastructure are not reported as absence of evidence. Raw
provider error bodies and invalid model responses are not displayed to users.

## What verification does and does not establish

Exact matching establishes that the quote appeared in a selected retrieved
passage. It does not establish that the source is true, that the quote fully
answers the question, or that all relevant passages were retrieved. The model
can still select an irrelevant or misleading excerpt. Prompt-injection text
is treated as untrusted data, and there are no write/tool capabilities in this
path, but prompt instructions alone are not a guarantee of semantic correctness.

The first version returns source excerpts. Free-form synthesis and
personalized recommendations would need additional support checks. Phase 5
should measure retrieval relevance, answer completeness, appropriate
abstention, conflicting sources, qualification/negation preservation and
adversarial documents before broadening the answer format.

During preparation, all 64 new offline tests passed. Combined with the 116
available document/embedding/storage tests, 180 passed with 177 subtests and
11 opt-in database skips under a simulated Windows environment-variable limit.
These preparation checks ran on Python 3.12. The user subsequently verified
317 passed, 11 skipped and 200 subtests on Windows Python 3.13, including the
existing Phase 0–3 modules. The 11 database tests passed separately.

The offline demo passed. A separate scratch check combined real cached BGE
embeddings and embedded PostgreSQL/pgvector with a scripted generation adapter
and checked source offsets. Groq request construction/errors were tested using
the installed groq==1.7.0 SDK with a mocked client. The user then ran --live
against the real Windows database and Groq: all three checks passed. The Room
answer cited normalized source offsets 58–268 (similarity about 0.812066); the
salary question returned model_insufficient_evidence, and empty scope returned
no_selected_documents without a model call. This verifies the observed smoke
scenario, not broad answer accuracy.

Provider references:

- https://console.groq.com/docs/text-chat
- https://console.groq.com/docs/model/openai/gpt-oss-120b
- https://console.groq.com/docs/structured-outputs

Windows tests and both demo modes have passed. Review the Phase 4 changes and
record the Git checkpoint before proceeding to Phase 5 evaluation. Commit/push
and remote synchronization are verified separately from the application checks;
see progress.md.
