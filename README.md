# CareerPilot

Agentic AI Career and Interview Assistant.

CareerPilot follows an AI-first approach: validate the standalone Python agent,
expose it through FastAPI, then integrate an Android application.

## Current status

Phases 0–4 are implemented and verified for the current local CLI scope.
Phase 4 adds local document retrieval and cited, extractive document answers.
Phase 5 evaluation is next. Phase 4 Git publication is tracked separately in
[development progress](docs/progress.md).

Verified on Windows with Python 3.13.16:

- 317 tests and 200 subtests passed; 11 database tests intentionally skipped
  by the default offline command.
- All 11 PostgreSQL integration tests passed when enabled separately.
- Real local embeddings, indexing and retrieval passed; a new Python process
  retrieved the stored vectors successfully.
- Offline and live PostgreSQL/Groq document-answer demos passed, including
  a cited answer, unsupported-question abstention and an empty document scope.

Implemented capabilities:

- Validated settings, Groq generation and deterministic skill comparison.
- Bounded planning, independent input verification and execution.
- Explicit SQLite profile save/load/replace/delete and opt-in agent reuse.
- UTF-8 `.txt`/`.md` ingestion and traceable character chunks.
- Local BGE CPU embeddings with token limits and embedding-space fingerprints.
- PostgreSQL/pgvector persistence, atomic document replacement, deletion and
  cosine retrieval scoped to an owner and selected documents.
- Document Q&A that validates exact quotations and derives source citations.

The skill-comparison agent and document-Q&A agent have separate explicit entry
points. Document passages never become verified profile skills or silently
update memory. LangGraph, general iterative planning, FastAPI, Android,
authentication and cloud deployment are not implemented yet.

## Stack

| Component | Current implementation / planned work |
| --- | --- |
| Agent | Python, Groq API, bounded planning and validated tool execution |
| Profile memory | Local SQLite |
| Document embeddings | FastEmbed 0.9.1, BAAI/bge-small-en-v1.5, CPU, 384 dimensions |
| Document storage | PostgreSQL 17 and pgvector 0.8.7 in local Docker |
| Backend API | FastAPI planned |
| Android | Kotlin, Compose, MVVM, StateFlow, Retrofit and Room planned |
| Deployment | Google Cloud Run planned; local database Compose setup verified |

## Development environment

From the repository root in PowerShell:

```powershell
py -3.13 -m venv backend\.venv
Set-Location backend
.\.venv\Scripts\python.exe -m pip install -e ".[dev,rag]"
.\.venv\Scripts\python.exe -m pip check

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
}

.\.venv\Scripts\python.exe -m pytest -q
```

Use the `.venv` interpreter directly if PowerShell blocks activation. The rag
extra adds fastembed==0.9.1 and psycopg[binary]==3.3.8. Direct dependencies are
pinned in pyproject.toml. requirements-dev-windows.txt is an earlier Windows
development snapshot; it has not been refreshed into a complete Phase 4
dependency lock. Linux deployment and a fresh production build remain to be
validated separately.

## Configuration

Local LLM configuration belongs in backend/.env. Commit only .env.example
with empty credentials. Environment variables use the CAREERPILOT_ prefix
and override dotenv values.

The loader requires an explicit dotenv path:

```python
from pathlib import Path
from careerpilot.config import load_settings

# When running from backend:
settings = load_settings(env_file=Path('.env'))
```

Calling load_settings() reads process environment variables and defaults only.
The default provider is mock, a configuration value rather than an implemented
mock client. Offline tests and demos explicitly inject scripted generation.

Groq development settings, edited only in backend/.env:

```dotenv
CAREERPILOT_APP_ENV=development
CAREERPILOT_LLM_PROVIDER=groq
CAREERPILOT_LLM_MODEL=openai/gpt-oss-120b
CAREERPILOT_LLM_API_KEY=<your-private-groq-key>
CAREERPILOT_LLM_TIMEOUT_SECONDS=30
```

The user has confirmed a Groq Free plan. Quotas and model availability are
provider-controlled; no paid fallback is implemented. Live configuration
validation does not verify the key with Groq. Automatic retries are disabled.

## Run document RAG locally

First follow [database setup](docs/phase4-database-setup.md) to create the ignored
infra/postgres/.env password file. With Docker Desktop running, start or resume
the database from the repository root:

```powershell
docker compose --env-file infra/postgres/.env -f infra/postgres/compose.yaml up -d --wait --wait-timeout 120
```

The database listens on 127.0.0.1:5433 and stores data in a named Docker volume.
Profile memory continues to use SQLite; it has not been migrated to PostgreSQL.

From backend, populate the local model cache on the first run if necessary:

```powershell
.\.venv\Scripts\python.exe scripts/embedding_demo.py --allow-download
```

Subsequent runs use cached files by default. Then:

```powershell
.\.venv\Scripts\python.exe scripts/retrieval_demo.py
.\.venv\Scripts\python.exe scripts/retrieval_demo.py --query-only
.\.venv\Scripts\python.exe scripts/grounded_answer_demo.py
.\.venv\Scripts\python.exe scripts/grounded_answer_demo.py --live
```

The first command indexes two illustrative sources. The query-only command
reads their stored vectors from a separate process. Grounded-answer demo
defaults to scripted offline fixtures; --live uses real retrieval and makes
two Groq calls. Live RAG sends the questions and selected passage text to Groq.
Its configuration path is resolved from the script to backend/.env.

Run the database tests explicitly from backend:

```powershell
$env:CAREERPILOT_RUN_DB_TESTS = "1"
try {
    .\.venv\Scripts\python.exe -m pytest tests/test_vector_store_integration.py -q
}
finally {
    Remove-Item Env:\CAREERPILOT_RUN_DB_TESTS -ErrorAction SilentlyContinue
}
```

## Public Python entry points

- careerpilot.llm.generate_text(settings, prompt)
- careerpilot.tool_calling.run_skill_comparison(settings, prompt)
- careerpilot.agent.run_agent(settings, request, ...): bounded skill comparison
  and learning advice, optionally using saved profile skills.
- careerpilot.document_agent.run_document_agent(settings, question, ...):
  explicit owner/document scope, one retrieval and at most one generation call.
- careerpilot.retrieval.RetrievalService: document indexing and scoped retrieval.

Skill comparison uses explicit structured lists and does not infer synonyms or
proficiency. Required skills never come from a saved goal or job title. The
successful comparison path uses at most two generation calls and one tool call.
Document answers contain verified exact source excerpts; quote matching checks
provenance, while relevance, completeness and source truth still need evaluation.

## Security and limits

- Never commit credentials, private documents, local environment files, model
  caches or database data. API keys belong only in the Python backend.
- SecretStr provides masking, not encryption. Do not log raw settings inputs,
  provider bodies or complete validation-error payloads.
- Retrieved text is untrusted data. Document Q&A has no tools or profile writes.
- Owner IDs are application filters, not authentication or row-level security.
- The local PostgreSQL bootstrap user has development privileges; production
  roles, access control, backups and deployment hardening remain future work.
- The English embedding model is not a verified multilingual solution. PDF/DOCX
  ingestion, approximate vector indexes and free-form document-answer synthesis
  are outside the current implementation.
- Similarity is not a confidence percentage. The demos are smoke checks, not
  broad evaluation or proof that every model response is correct.

## Project records

- [Progress and roadmap](docs/progress.md)
- [Phase 3 profile memory](docs/phase3-memory.md)
- [Local embeddings](docs/phase4-embeddings.md)
- [PostgreSQL setup](docs/phase4-database-setup.md)
- [Vector storage and retrieval](docs/phase4-vector-store.md)
- [Cited document answers](docs/phase4-grounded-answers.md)
- [ADR 0001: AI-first foundation](docs/decisions/0001-ai-first-foundation.md)
- [ADR 0002: original provider decision](docs/decisions/0002-free-tier-provider.md)
- [ADR 0003: Groq replacement](docs/decisions/0003-groq-phase1.md)
- [ADR 0004: bounded planning](docs/decisions/0004-bounded-planning-phase2.md)
- [ADR 0005: local profile memory](docs/decisions/0005-local-profile-memory-phase3.md)
- [ADR 0006: local document RAG](docs/decisions/0006-local-document-rag-phase4.md)
