# CareerPilot development progress

Updated: 2026-11-06

## Current phase

Phase 4 local document RAG is implemented and verified in the current Windows
CLI scope. This includes ingestion, local embeddings, PostgreSQL/pgvector
storage, scoped retrieval and extractive document answers with checked quotes.
The user confirmed the full offline suite, database integration tests,
separate-process retrieval, and the live PostgreSQL/Groq answer demo.

Phase 4 Git commit/push verification is pending at the time of this record.
No Phase 4 hash or remote state is asserted. Phase 5 evaluation is next.

## Verified Git checkpoints

| Phase | Evidence |
| --- | --- |
| 0 | c532502, completed and pushed |
| 1 | f73de04, completed and pushed; 39 tests at that checkpoint |
| 2 | 0a5f31c, completed and pushed; 73 tests |
| 3 | 9fab025, Complete Phase 3 persistent profile memory and agent integration; clean main synchronized with origin/main (0 0) before Phase 4 |
| 4 | Implementation and Windows verification complete; commit and push not yet observed |

Git history and terminal outputs remain the source of truth for publication.

## Phase 4 verification evidence

| Checkpoint | Observed Windows result |
| --- | --- |
| Phase 3 baseline before RAG | 137 passed, 23 subtests passed |
| Documents | 20 new tests, 150 subtests; full suite 157 passed, 173 subtests |
| Embeddings | 30 new tests, 27 subtests; full suite 187 passed, 200 subtests |
| Real CPU embedding demo | PASS; 3 chunks; document/query dimensions 384; vector norms 1.0 |
| Dependency compatibility | pip check: No broken requirements found |
| Docker database | PostgreSQL container healthy; localhost 5433 mapped to container 5432 |
| Extension and TCP connection | Database careerpilot, pgvector 0.8.7, 384-dimensional vector, self cosine similarity 1.0 |
| Storage offline tests after Windows-ID fix | 253 passed, 11 skipped, 200 subtests passed in 1.48s |
| Native PostgreSQL integration tests | 11 passed in 1.58s |
| Real index-and-query demo | PASS; 2 documents, 2 chunks; Room source ranked first |
| Separate query-only process | PASS; existing vectors retrieved; owner/document filters and source offsets passed |
| Grounding and document agent tests | 64 passed in 0.36s |
| Final offline suite | 317 passed, 11 skipped, 200 subtests passed in 1.47s |
| Offline grounded-answer demo | PASS; scripted citation, unsupported-question and empty-scope checks |
| Live PostgreSQL/Groq grounded-answer demo | PASS; cited Room answer, salary-question abstention, empty scope with no model call |

The 317 default tests comprise the 137-test Phase 3 baseline plus 20 document,
30 embedding, 66 storage/settings/identity and 64 grounding/agent/provider
tests. The 11 database integration tests were enabled and verified separately.
Subtests are additional checks, not additional top-level tests. The default
skips are intentional and do not indicate failing database tests.

The live answer quoted the Android source at normalized character offsets
58–268, with similarity approximately 0.812066 and the stored document hash.
The unsupported salary question returned insufficient_evidence with reason
model_insufficient_evidence. Empty selection returned no_selected_documents
with model_called=false. These verify the observed scenarios, not general
semantic accuracy or an evaluated relevance threshold.

## Corrections verified during Phase 4

- Large parametrized test strings originally became test IDs and exceeded
  Windows' environment-variable length limit. Explicit short IDs fixed the
  setup/teardown errors; the Windows storage and full suites then passed.
- The live document demo initially called load_settings() without a dotenv
  path and selected the default mock provider. It now explicitly loads
  backend/.env relative to the script's location. The subsequent live demo passed.
- Initial model-download connection retries recovered; the real model passed
  the shape/normalization check and later retrieval demos.

## Completed capabilities and boundaries

- Foundation: editable package, validated settings and secret handling.
- Groq generation, deterministic compare_skills and bounded tool calling.
- Bounded planning, independent input verification, execution and final response.
- SQLite profile save, load, replacement and deletion, separated by exact user ID.
- Opt-in profile retrieval; explicit skills override saved current skills.
- Deterministic clarification when structured memory/comparison inputs are missing.
- UTF-8 .txt/.md ingestion, normalized text hashes, stable chunks and offsets.
- Local 384-dimensional BGE embeddings with token checks and space fingerprints.
- PostgreSQL document/chunk persistence, atomic replacement and cascading deletion.
- Exact cosine retrieval with explicit owner/document scope and compatible spaces.
- Extractive document answers with validated quote text and derived citations.
- Zero-call handling of empty/no-hit scopes and rejection of malformed model output.

The document agent is an explicit entry point alongside the skill-comparison
agent. It does not route through the comparison planner, infer skill lists or
modify profiles. SQLite profile memory and PostgreSQL document storage coexist.

## Configuration and dependencies

- Repository: https://github.com/bornstar-sys/CareerPilot
- Windows development interpreter: Python 3.13.16.
- Provider/model: groq / openai/gpt-oss-120b; user-confirmed Free plan, no paid fallback.
- Existing direct dependencies: Pydantic 2.14.0, pydantic-settings 2.15.0,
  Groq 1.7.0 and development pytest 9.1.1.
- New rag extra: fastembed==0.9.1 and psycopg[binary]==3.3.8.
- Model: BAAI/bge-small-en-v1.5, CPU, 384 dimensions; cache-only by default.
- Database image: pgvector/pgvector:0.8.7-pg17-trixie, local named volume.
- LLM credentials: ignored backend/.env, loaded only when explicitly selected.
- Database credentials: infra/postgres/.env; git check-ignore confirmed exclusion.
- Tracked infrastructure candidates: .env.example, .gitignore, compose.yaml,
  and init/01-enable-vector.sql. No actual password file appeared as untracked.

Direct pins do not constitute a complete transitive dependency lock. The older
requirements-dev-windows.txt snapshot was not updated in this phase. Model or
runtime changes can change the embedding fingerprint and require reindexing.

## Earlier memory verification record

The Phase 3 record included a Windows restart with a clean, synchronized main
and 73 tests passing; storage checks reached 97 passed with 23 subtests. The
integrated preparation workspace reported 137 passed and 23 subtests on Linux
Python 3.13.17. Windows integration then passed 137 tests and 23 subtests.

Separate-process save, reuse and deletion checks passed. The offline memory
demo reported source=memory, saved goal sent=True and status=compared. The live
Groq comparison matched Kotlin and reported Room and REST API missing from the
saved list, with matched_count=1 and required_count=3. The response preserved
that distinction from proficiency and labeled timelines illustrative.

## Limits retained for evaluation and later phases

- None means unknown current skills; [] explicitly means no current skills.
  Required skills come from current structured input, never a goal or title.
- Agent calls never silently save inferred facts, model output or transcripts.
- Missing memory inputs use zero generation calls; clarification uses one;
  successful comparison uses two plus one tool execution. Document Q&A uses
  one retrieval and at most one generation call. There are no automatic retries.
- IDs are application lookup/filter keys, not authentication or row-level security.
- SQLite data is local plaintext. Production roles, encryption, backup/restore,
  synchronization and cloud deployment are not verified.
- Planning remains a bounded branch; LangGraph, iterative loops and automatic
  clarification resumption are not implemented.
- Exact quote matching verifies provenance, not relevance, truth or completeness.
  Adversarial documents, conflicting evidence and abstention need systematic evaluation.
- The English model is not a verified multilingual solution. PDF/DOCX ingestion,
  approximate vector indexes and free-form document-answer synthesis are out of scope.
- Similarity is not confidence; free-tier quotas and access remain provider-controlled.

## Phase 4 closeout

- [x] Verify document ingestion and local embeddings on Windows.
- [x] Verify Docker, pgvector and Python TCP connectivity.
- [x] Pass native PostgreSQL integration tests and separate-process retrieval.
- [x] Pass the full offline suite and grounded-answer fixture demo.
- [x] Verify the live document answer and both abstention cases.
- [x] Prepare README, component documentation and ADR updates with actual results.
- [ ] Apply documentation closeout files and review the staged diff.
- [ ] Commit and push Phase 4, then verify clean main and HEAD...origin/main = 0 0.

No new behavioral checks are claimed by this documentation update. Git
publication will be verified from the resulting commit/push/status output.

## Roadmap

| Phase | Scope | Status |
| --- | --- | --- |
| 0 | Foundation | Complete and pushed |
| 1 | LLM integration and tool calling | Complete and pushed |
| 2 | Bounded planning and execution | Complete and pushed |
| 3 | Persistent profile memory | Complete and pushed; 9fab025 |
| 4 | Local document RAG and cited extractive answers | Implemented and verified; Git closeout pending |
| 5 | Evaluation and mock interviews | Next, not started |
| 6 | FastAPI backend | Not started |
| 7 | Android app | Not started |
| 8 | Authentication, security and deployment | Not started |
| 9 | Final testing, documentation and portfolio preparation | Not started |
