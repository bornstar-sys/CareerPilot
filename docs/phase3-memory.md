# Phase 3 memory: usage and verification

## Save and update explicitly

Run Python from backend with the project's interpreter. Storage itself makes
no API calls. A new save for the same ID fully replaces that profile.

```python
from pathlib import Path
from careerpilot.memory import MemoryStore, UserProfile

store = MemoryStore(Path("data/memory.sqlite3"))
store.save_profile(UserProfile(
    user_id="demo-user",
    current_skills=["Kotlin", "Jetpack Compose"],
    career_goal="Become an Android developer",
))

profile = store.get_profile("demo-user")
if profile is not None:
    store.save_profile(UserProfile(
        user_id=profile.user_id,
        current_skills=["Kotlin", "Jetpack Compose", "Room"],
        career_goal=profile.career_goal,
    ))
```

Keep every field you want to retain during replacement. current_skills=None
clears knowledge of skills; [] records explicitly none. career_goal=None clears
the goal. store.delete_profile("demo-user") deletes that exact profile.

## Reuse in a later live agent call

```python
from pathlib import Path
from careerpilot.agent import run_agent
from careerpilot.config import load_settings
from careerpilot.memory import MemoryStore

settings = load_settings(Path(".env"))
store = MemoryStore(Path("data/memory.sqlite3"))
result = run_agent(
    settings, "Create a short learning plan.",
    memory_store=store, user_id="demo-user",
    required_skills=["Kotlin", "Room", "REST API"],
)
print(result.current_skills_source)
print(result.execution.tool_result)
print(result.answer)
```

This uses the existing Groq provider, at most twice, if sufficient facts exist.
It does not update memory. A one-request override uses supplied_skills instead:

```python
from careerpilot.tools import CompareSkillsInput

result = run_agent(
    settings, "Compare these lists for this request.",
    memory_store=store, user_id="demo-user",
    supplied_skills=CompareSkillsInput(
        current_skills=["Java"], required_skills=["Java", "SQL"],
    ),
)
```

Do not pass required_skills and supplied_skills together. Required skills must
come from structured current input, never from a title or saved goal. Invalid
data fails before model calls. Missing facts in memory mode return clarification
without a model call. Calls without memory arguments retain the Phase 2 API.

## Offline Windows checks

```powershell
cd D:\Projects\CareerPilot\backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\memory_demo.py save
.\.venv\Scripts\python.exe scripts\memory_demo.py compare
```

Expected combined result: 137 passed, 23 subtests passed, if all package files
are applied and there are no unrelated new tests.

The commands start separate processes. The demo uses fictional phase3-demo-user
in backend/data/phase3-demo.sqlite3. Save replaces only that demo profile.
Compare defaults to offline mode: model responses are mocked; persistence,
plan parsing, independent input checks and the tool are real.

Expected comparison: source=memory, saved goal sent=True, status=compared,
matched Kotlin, missing from saved list Room and REST API.

## Live check using the existing free provider

After the save command, explicitly choose live mode:

```powershell
.\.venv\Scripts\python.exe scripts\memory_demo.py compare --live
```

This reads backend/.env, uses the existing model/key and makes at most two
generation requests without retries. Keep the key in .env. No provider change
or paid fallback is required.

Check source=memory and the same deterministic tool result. The answer should
mention the saved list, distinguish missing list entries from proof of low
proficiency, and give relevant advice without claiming a profile update.
A model may clarify or return an invalid plan: record the actual outcome.
If quota/access fails, keep live verification pending rather than calling it
successful. Offline verification remains a separate result.

Optional demo-profile cleanup:

```powershell
.\.venv\Scripts\python.exe scripts\memory_demo.py delete
```

## Final Git checkpoint, after verification

Record actual Windows/live results in docs/progress.md, then review:

```powershell
cd D:\Projects\CareerPilot
git status --short
git diff --check
git diff --stat
git check-ignore backend/data/phase3-demo.sqlite3
```

After checks pass and the diff is reviewed:

```powershell
git add backend/src/careerpilot/memory.py backend/src/careerpilot/agent.py backend/src/careerpilot/planner.py
git add backend/tests/test_memory.py backend/tests/test_agent_memory.py backend/scripts/memory_demo.py
git add docs/progress.md docs/decisions/0005-local-profile-memory-phase3.md docs/phase3-memory.md
git diff --cached --check
git diff --cached --stat
git commit -m "Complete Phase 3 persistent profile memory and agent integration"
git push origin main
git status -sb
git rev-list --left-right --count HEAD...origin/main
```

If you appended /backend/data/ in step 1, the existing backend/data/ already
covers the folder. Keep and explicitly stage the reviewed .gitignore change,
or remove only your duplicate line. Preserve other rules. Do not stage .env,
.venv, databases or downloaded ZIPs. Confirm the checkpoint from actual output.
