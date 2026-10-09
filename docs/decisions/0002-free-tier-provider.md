# ADR 0002: Free-tier LLM provider

Date: 2026-10-10
Status: Accepted for initial development

## Context

The project must use free-tier API access during learning.
Tool calling and structured outputs are required.

## Decision

Use the Gemini Developer API with gemini-3.5-flash-lite as the
initial configured model, subject to live access verification.

Keep the Google project on the Free tier without enabling billing.
Keep credentials in ignored backend/.env.
Retain mock defaults in .env.example.
Use fictional or sanitized development data.

## Consequences

Free-tier quota and availability may change.
Quota exhaustion must produce a controlled error, not a paid fallback.
Automated tests should use mock responses once the client is implemented.
Live key validation and model access checks belong to Phase 1.
Provider-specific code will remain separate from agent logic.
