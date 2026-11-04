# CareerPilot development progress

Updated: 2026-11-05

## Current phase

Phase 3 persistent profile memory implementation and verification are complete.
The user confirmed the integrated Windows suite, separate-process offline demo,
and live Groq comparison on 2026-11-05. Phase 4 RAG is the next planned phase
and has not started. Git publication is verified separately from commit/push
output; these records do not assert an unobserved commit or remote state.

## Verified checkpoints

| Checkpoint | Evidence |
|---|---|
| Phase 0 | c532502, completed and pushed |
| Phase 1 | f73de04, completed and pushed; 39 tests at that checkpoint |
| Phase 2 | 0a5f31c, completed and pushed; 73 tests |
| Windows restart | Python 3.13.16; clean main; HEAD...origin/main = 0 0; 73 passed in 0.56s |
| Windows Phase 3 storage | User reported 97 passed, 23 subtests passed in 0.77s |
| Integrated workspace | Linux/Python 3.13.17; 137 passed, 23 subtests passed in 2.16s |
| Separate-process workspace demo | Save, then agent reuse in a new process, then deletion succeeded |
| Windows integration | Python 3.13.16; 137 passed, 23 subtests passed in 1.37s |
| Windows offline memory demo | Separate save/compare commands; source=memory; saved goal sent=True; status=compared |
| Windows live Groq demo | source=memory; saved goal sent=True; status=compared; matched Kotlin; missing Room and REST API |

The integrated count comprises 73 existing tests, 27 storage tests, and 37
memory integration cases. The first storage increment had 24 storage tests.
Subtests are additional checks inside those tests.

Workspace direct dependencies match unchanged pyproject.toml: Pydantic 2.14.0,
pydantic-settings 2.15.0, Groq 1.7.0, pytest 9.1.1. The dependency compatibility
check passed. This is not the exact Windows lock environment. No live API call
was made during workspace verification; generation was mocked.

## Completed capabilities

- Foundation: editable package, validated settings and secret handling.
- Groq generation, compare_skills and bounded tool calling.
- Bounded planning, independent input verification, execution and final response.
- Explicit SQLite profile save, load, replacement and deletion.
- Persistent skills and optional career goal, separated by exact user ID.
- Agent opt-in profile retrieval; explicit skill input overrides saved skills.
- Input-source metadata and saved-goal context in the response evidence.
- Deterministic clarification for missing structured facts in memory mode.
- Regression, persistence, isolation, failure and integration tests.

## Active provider

- Repository: https://github.com/bornstar-sys/CareerPilot
- Provider/model: groq / openai/gpt-oss-120b
- Plan: Free, confirmed by the user; no paid fallback
- Credentials: ignored backend/.env
- Development data: fictional or sanitized

Gemini initially returned a project access denial; ADR 0003 supersedes that
provider decision. Earlier live text-generation, tool-calling, learning-plan
and clarification checks passed. The Phase 3 live demo also passed on the
user's Windows machine: matched_count=1 and required_count=3. The response
acknowledged the saved skills source, preserved the comparison, distinguished
missing list entries from proficiency, and labeled its timelines illustrative.
It suggested REST API practice followed by Room with practical exercises.
This verifies the observed scenario, not all possible model responses.

## Memory behavior and limits

None means current skills are unknown; [] means explicitly no current skills.
Required skills always come from the current structured comparison input.
Goals/job titles never supply required skills. Agent calls read profiles but
never silently save inferred facts, model output, overrides or transcripts.

Missing memory inputs use zero generation calls. A model clarification uses
one call; a successful comparison uses two generation calls and one tool call.
No automatic retries, iterative loops or clarification resumption are added.

- Profile IDs are lookup keys, not authentication or access control.
- SQLite files are local plaintext data. No production encryption,
  synchronization or PostgreSQL migration is implemented.
- Saves replace entire profiles with last-writer-wins behavior.
- Invalid old profiles outside comparison limits fail validation; there is
  no silent truncation. Valid step-1 profiles remain readable.
- No RAG, arbitrary planning, transcript memory or automatic clarification resumption.
- Planning is a bounded branch, not LangGraph or an iterative agent loop.
- mock remains a settings default; tests/demo explicitly mock generation calls.
- Skill comparison does not infer synonyms or proficiency.
- Generated advice/source wording can be inaccurate; timelines are illustrative.
- Free-tier quotas/access are provider-controlled; deployment remains unverified.

## Phase 3 verification checklist

- [x] Apply integration files on Windows and pass the combined suite.
- [x] Run save and compare as separate commands and inspect the tool result.
- [x] Verify the live comparison and inspect the generated response.
- [x] Record actual Windows/live results here.

For the Git checkpoint, review/stage only the intended source, tests and docs,
check that local data is ignored, then commit/push and verify synchronization.
The procedure is documented in docs/phase3-memory.md. No commit hash is invented
here; Git history and the resulting terminal output are the source of truth.

## Roadmap

| Phase | Scope | Status |
|---|---|---|
| 0 | Foundation | Complete and pushed |
| 1 | LLM integration and tool calling | Complete and pushed |
| 2 | Bounded planning and execution | Complete and pushed |
| 3 | Persistent profile memory | Implemented and verified offline and live |
| 4 | RAG and vector database | Not started |
| 5 | Evaluation and mock interviews | Not started |
| 6 | FastAPI backend | Not started |
| 7 | Android app | Not started |
| 8 | Authentication, security and deployment | Not started |
| 9 | Final testing, documentation and portfolio preparation | Not started |
