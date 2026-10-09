# ADR 0001: AI-first project foundation

Date: 2026-10-10
Status: Accepted

## Context

CareerPilot must validate its agent independently before Android development.
The project specification defines features and architecture.
The user's AI-first roadmap defines implementation order.

## Decisions

1. Use one repository for the Python backend, documentation, and future Android app.
2. Develop the agent as the careerpilot Python package under backend/src.
3. Use Python 3.13 with an isolated virtual environment.
4. Use pyproject.toml for package metadata and direct dependency pins.
5. Capture the verified Windows development dependencies separately.
6. Use Pydantic Settings for typed configuration.
7. Load dotenv files explicitly; environment variables override dotenv values.
8. Default to mock configuration during foundation work.
9. Keep credentials outside Git and exclude keys from settings serialization.
10. Use pytest while retaining the existing unittest-compatible smoke test.
11. Implement one agent first; add multiple agents only if justified.
12. Require user confirmation before advancing to the next phase.

## Consequences

The future CLI and FastAPI service can share agent code.
Foundation tests do not require paid API calls.
Provider credentials and available model names still need live verification.
Production dependency locking and Linux validation remain future work.
Security and tests are implemented throughout development.
