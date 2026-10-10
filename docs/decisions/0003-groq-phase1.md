\# ADR 0003: Groq for Phase 1



Date: 2026-10-11

Status: Accepted

Supersedes: ADR 0002



\## Context



Gemini live requests returned HTTP 403 PERMISSION\_DENIED:

"Your project has been denied access. Please contact support."



AI Studio showed Restricted and requested billing setup.

The project must remain on free-tier access during development.



\## Decision



Use Groq with openai/gpt-oss-120b and groq==1.7.0.

The user verified the Groq Free plan.

Live text generation and tool calling both passed.



Retain mock defaults in .env.example.

Store the Groq key only in ignored backend/.env.

Keep API keys exclusively in the Python backend.



Use a bounded tool-calling flow:

1\. Request exactly one compare\_skills function call.

2\. Validate its name and arguments before execution.

3\. Execute the deterministic Python function.

4\. Return the result using the matching tool-call ID.

5\. Request a final explanation with further tool calls disabled.



Disable automatic retries and provide no paid fallback.



\## Verification



\- 39 offline tests passed.

\- pip check reported no broken requirements.

\- Integrated text generation passed.

\- Live comparison returned Kotlin as matched and Room and REST API

&#x20; as missing from the supplied current-skills list.

\- The model explanation agreed with the computed result.

\- backend/.env is ignored and not tracked.



\## Limitations



Free-tier access and quotas may change.

Comparison uses skill names, not semantic equivalence or proficiency.

Schema validation does not guarantee faithful extraction for every prompt.

The final explanation remains model-generated.

The live example verifies one scenario, not broad model reliability.

Autonomous planning, retries, persistent memory, and RAG are future work.

