# 0005: Explicit persistent profiles and bounded agent reuse

Status: implemented and verified offline and live on 2026-11-05.
Extends ADR 0004's independent-input boundary. Git publication is confirmed
separately from commit/push output.

## Storage

Use Python sqlite3 and the existing Pydantic dependency. A dedicated SQLite
file stores JSON profiles keyed by exact case-sensitive user ID. No new package
or paid service is introduced. PostgreSQL remains in the later backend plan.

UserProfile holds user_id, current_skills and career_goal. Unknown skills are
None; [] explicitly supplies no skills. Skill values reuse the comparison
tool's SkillName validation: strict strings, outer whitespace removal, at most
50 skills and 100 characters per name. Goals are optional strings up to 1000
characters. Unknown fields, blank strings and NUL are rejected.

MemoryStore saves/replaces whole profiles, loads validated profiles and deletes
exact IDs. Writes commit in transactions, SQL values use parameters, and every
operation closes its connection. Every save revalidates its immutable input
snapshot. Invalid stored data raises MemoryDataError; database errors propagate.

The path resolves once at initialization. Schema version 1 uses user_version;
unsupported versions fail. The physical table schema remains unchanged from
step 1. Valid old JSON loads; stored [] keeps its explicit-empty meaning, and
JSON null now means unknown. The original intent of old [] values cannot be
recovered. Old profiles exceeding the new tool limits must be corrected and
resaved explicitly; data is not silently truncated or reset.

## Integration and precedence

The existing run_agent(settings, request, supplied_skills=...) interface remains
valid. Memory requires both memory_store and user_id. Without them, the agent
does not read or create a database. Supplying only one is an error.

1. supplied_skills supplies both lists and overrides saved current skills.
2. Otherwise, required_skills comes from this call and current skills come from
   the selected saved profile. Both input modes together are rejected.
3. Missing profiles, unknown skills or missing structured requirements cause
   deterministic clarification without a model call.
4. Explicitly empty current skills are valid; empty requirements are invalid.
5. A saved goal is optional advice context, never required-skill evidence.
6. Response instructions prioritize a newly stated goal in the current request;
   prose adherence remains model-dependent and the stored goal is not changed.

One database read supplies a snapshot. Resolved skills are validated through
CompareSkillsInput and independently passed to the unchanged executor. Planned
arguments must equal that snapshot before the deterministic comparison runs.
Model-generated arguments cannot authorize additional skills.

Saved goal and source metadata enter prompts as JSON data. The application
does not send the lookup ID or unrelated profiles. User-chosen text may still
contain personal data, and JSON alone does not guarantee prompt adherence.

AgentResult.current_skills_source reports supplied, memory or none, including
on clarification results. used_saved_goal means the non-null saved goal was
sent to generation, not that the model was verified to use it correctly.

## Writes, limits and boundaries

Agent calls never write/delete profiles or infer saved facts. Callers explicitly
save complete profiles; per-call overrides do not persist. No credential,
transcript or generated advice is automatically stored.

At most two generation calls and one tool call are allowed: missing memory
facts use zero, model clarification uses one, successful comparison uses two.
No retries, execution loops or automatic clarification resumption are added.
Invalid input, storage failures, invalid plans, mismatches, tool failures and
generation failures stop the workflow rather than fabricating success.

Use backend/data/ for local databases; the project already ignores it. IDs are
not authentication: a future service must derive them from verified identities.
Files are plaintext; full replacement writes are last-writer-wins. Production
authorization, encryption, conflict handling and migration remain future work.

## Verification

137 tests and 23 subtests passed on Linux/Python 3.13.17 with pinned direct
dependencies. Real SQLite, planner parsing, execution and comparison were tested
with mocked generation. Separate-process save/compare/delete succeeded.
The user subsequently confirmed 137 tests and 23 subtests passed in 1.37s on
Windows/Python 3.13.16, followed by separate-process save and offline comparison.
The live Groq demo returned source=memory, saved goal sent=True, status=compared,
matched Kotlin, missing Room and REST API, and counts 1/3. Its response
acknowledged the saved list, distinguished missing list entries from proficiency,
and labeled suggested timelines illustrative. Live execution occurred on the
user's PC; no live request was made in the workspace. This is evidence for the
observed scenario and does not guarantee correctness of future generated advice.

References:

- https://docs.python.org/3.13/library/sqlite3.html
- https://docs.pydantic.dev/latest/concepts/validators/
- https://docs.pydantic.dev/latest/concepts/models/
