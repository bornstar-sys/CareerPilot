# CareerPilot

Agentic AI Career and Interview Assistant.

CareerPilot is being developed using an AI-first approach:
validate a standalone Python agent, expose it through FastAPI,
then integrate an Android application.

## Current status

Phase 0 is in progress.

Implemented and verified:
- Python package with editable installation.
- Validated environment and dotenv configuration.
- Mock provider configuration as the default.
- Required model and API key validation for live providers.
- Secret exclusion from settings representations and serialization.
- 12 passing foundation and configuration tests.

LLM calls, agent workflows, APIs, and Android screens are not implemented yet.

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

## Project records

- docs/progress.md: phase status and verification evidence.
- docs/decisions/0001-ai-first-foundation.md: initial architecture decisions.
