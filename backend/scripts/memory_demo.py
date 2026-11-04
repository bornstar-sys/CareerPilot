"""Demonstrate saving in one process and agent reuse in a later process."""

import argparse
import json
from pathlib import Path
from unittest.mock import patch

from careerpilot.agent import run_agent
from careerpilot.config import Settings, load_settings
from careerpilot.memory import MemoryStore, UserProfile


BACKEND = Path(__file__).resolve().parents[1]
DEMO_USER = "phase3-demo-user"
REQUIRED = ["Kotlin", "Room", "REST API"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["save", "compare", "delete"])
    parser.add_argument("--live", action="store_true", help="Use the configured Groq provider for compare.")
    args = parser.parse_args()
    if args.live and args.action != "compare":
        parser.error("--live applies only to compare")

    store = MemoryStore(BACKEND / "data" / "phase3-demo.sqlite3")
    if args.action == "save":
        store.save_profile(UserProfile(
            user_id=DEMO_USER,
            current_skills=["Kotlin", "Jetpack Compose"],
            career_goal="Become an Android developer",
        ))
        print("Saved fictional demo profile. Run compare in a new command/process.")
        return
    if args.action == "delete":
        print("Deleted demo profile." if store.delete_profile(DEMO_USER) else "No demo profile to delete.")
        return

    profile = store.get_profile(DEMO_USER)
    if profile is None:
        parser.error("No demo profile. Run the save action first.")

    def run(settings):
        return run_agent(settings, "Create a short learning plan for the missing skills.",
            memory_store=store, user_id=DEMO_USER, required_skills=REQUIRED)

    if args.live:
        print("LIVE mode: at most two Groq generation calls; no automatic retries.")
        result = run(load_settings(BACKEND / ".env"))
    else:
        print("OFFLINE mode: model responses are mocked; SQLite, plan validation and the tool are real.")
        response = json.dumps({"decision": {
            "action": "compare",
            "arguments": {"current_skills": list(profile.current_skills or ()), "required_skills": REQUIRED},
            "output": "learning_plan",
        }})
        with patch("careerpilot.planner.generate_text", return_value=response), patch(
            "careerpilot.agent.generate_text",
            return_value="Offline placeholder. Inspect the real tool results below; no live advice was generated.",
        ):
            result = run(Settings(_env_file=None))

    print("Current skills source:", result.current_skills_source)
    print("Saved goal sent as context:", result.used_saved_goal)
    print("Status:", result.execution.status)
    print("Tool result:", json.dumps(result.execution.tool_result, ensure_ascii=False))
    print("Answer:", result.answer)


if __name__ == "__main__":
    main()
