# CareerPilot

Agentic AI Career and Interview Assistant.

CareerPilot is being developed using an AI-first approach:
validate a standalone Python agent, expose it through FastAPI,
then integrate an Android application.

## Current status

Phase 1: LLM Integration and Tool Calling is implemented and verified.
Phase 2 requires explicit user confirmation.

Implemented and verified:
- Editable Python package with validated Pydantic configuration.
- Mock configuration defaults; no credentials required for automated tests.
- Groq integration using groq==1.7.0 and openai/gpt-oss-120b.
- User-confirmed Groq Free plan.
- Live text generation through the reusable client.
- Validated, deterministic compare_skills tool.
- Live tool-call round trip with a final model explanation.
- 39 passing offline tests.

The tool-calling flow performs at most two API requests and one tool
execution. Automatic retries are disabled. Skill comparison ignores case
and surrounding whitespace but does not infer synonyms or proficiency.

Planning, persistent memory, RAG, FastAPI, and Android are not implemented.

## Planned stack

- Agent: Python, LLM APIs, LangGraph, tool calling, RAG.
- Backend: FastAPI.
- Persistence: PostgreSQL and pgvector.
- Android: Kotlin, Jetpack Compose, MVVM, StateFlow, Retrofit, Room.
- Deployment: Docker and Google Cloud Run.

## Development environment

Verified on Windows with Python 3.13.16.

From the repository root, using PowerShell:

```powershell
py -3.13 -m venv backend\.venv
Set-Location backend
.\.venv\Scripts\python.exe -m pip install -r requirements-dev-windows.txt
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pip check

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
}

.\.venv\Scripts\python.exe -m pytest -v
```

The requirements file captures the Windows development environment.
Linux and production installation will be validated separately.

## Configuration

Local configuration belongs in backend/.env.
Commit only .env.example with empty credentials.

Environment variables use the CAREERPILOT_ prefix and override dotenv values.
Load a dotenv file explicitly through load_settings(Path(".env")).
Calling load_settings() reads environment variables and defaults only.

The default provider is mock. No provider account is required for tests.
Live provider settings require a model name and nonblank API key.
Configuration validation does not verify credentials with a provider.

## Security

- Never commit credentials, private documents, or local environment files.
- API keys belong only in the Python backend.
- SecretStr provides masking, not encryption.
- Do not log raw settings inputs or complete validation error payloads.
- Uploaded documents will be treated as untrusted data.

### Groq development configuration

After copying backend/.env.example to backend/.env, configure locally:

    CAREERPILOT_APP_ENV=development
    CAREERPILOT_LLM_PROVIDER=groq
    CAREERPILOT_LLM_MODEL=openai/gpt-oss-120b
    CAREERPILOT_LLM_API_KEY=<your-private-groq-key>
    CAREERPILOT_LLM_TIMEOUT_SECONDS=30

Keep .env.example on mock defaults with empty credentials.
The mock value is a configuration default, not an implemented mock client.

From backend, use .\.venv\Scripts\python.exe directly if PowerShell
blocks virtual-environment activation.

Public Python entry points:
- careerpilot.llm.generate_text(settings, prompt)
- careerpilot.tool_calling.run_skill_comparison(settings, prompt)

The comparison entry point expects both current and required skill lists.
It explicitly requires compare_skills; autonomous tool selection and
multi-step planning are future work.

Free-tier quotas and model availability may change. No paid fallback is
implemented. API failures are surfaced as controlled LLMError messages.

## Project records

- docs/progress.md: phase status and verification evidence.
- docs/decisions/0001-ai-first-foundation.md: initial architecture decisions.
- docs/decisions/0002-free-tier-provider.md: original Gemini decision.
- docs/decisions/0003-groq-phase1.md: verified Groq replacement.

