"""Offline persistence tests; also discoverable by pytest."""

from contextlib import closing
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from pydantic import ValidationError

from careerpilot.memory import MemoryDataError, MemoryStore, UserProfile


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "data" / "memory.sqlite3"
        self.store = MemoryStore(self.path)
        self.profile = UserProfile(
            user_id="demo-user", current_skills=["Kotlin", "Jetpack Compose"],
            career_goal="Become an Android developer",
        )

    def replace_payload(self, payload):
        with closing(sqlite3.connect(self.path)) as connection:
            with connection:
                connection.execute(
                    "UPDATE profiles SET profile_json = ? WHERE user_id = ?",
                    (payload, self.profile.user_id),
                )

    def test_new_store_has_no_profile(self):
        self.assertIsNone(self.store.get_profile("unknown"))

    def test_save_and_load_round_trip(self):
        self.assertEqual(self.store.save_profile(self.profile), self.profile)
        self.assertEqual(self.store.get_profile("demo-user"), self.profile)

    def test_data_survives_reopening_store(self):
        self.store.save_profile(self.profile)
        self.assertEqual(MemoryStore(self.path).get_profile("demo-user"), self.profile)

    def test_data_survives_separate_python_process(self):
        self.store.save_profile(self.profile)
        env = os.environ.copy()
        source = str(Path(__file__).resolve().parents[1] / "src")
        env["PYTHONPATH"] = os.pathsep.join(filter(None, [source, env.get("PYTHONPATH")]))
        result = subprocess.run(
            [sys.executable, "-c",
             "import sys; from careerpilot.memory import MemoryStore; "
             "p = MemoryStore(sys.argv[1]).get_profile('demo-user'); "
             "print(p.model_dump_json())", str(self.path)],
            env=env, text=True, capture_output=True, check=True, timeout=15,
        )
        self.assertEqual(UserProfile.model_validate_json(result.stdout), self.profile)

    def test_update_replaces_profile(self):
        self.store.save_profile(self.profile)
        changed = UserProfile(user_id="demo-user", current_skills=["Kotlin", "Room"])
        self.store.save_profile(changed)
        self.assertEqual(self.store.get_profile("demo-user"), changed)

    def test_explicit_replacement_can_clear_fields(self):
        self.store.save_profile(self.profile)
        self.store.save_profile(UserProfile(user_id="demo-user"))
        loaded = self.store.get_profile("demo-user")
        self.assertIsNone(loaded.current_skills)
        self.assertIsNone(loaded.career_goal)

    def test_users_stay_separate_during_update(self):
        other = UserProfile(user_id="other-user", current_skills=["Java"])
        self.store.save_profile(self.profile)
        self.store.save_profile(other)
        self.store.save_profile(UserProfile(user_id="demo-user", current_skills=["Room"]))
        self.assertEqual(self.store.get_profile("other-user"), other)

    def test_delete_only_removes_requested_user(self):
        other = UserProfile(user_id="other-user", current_skills=["Java"])
        self.store.save_profile(self.profile)
        self.store.save_profile(other)
        self.assertTrue(self.store.delete_profile("demo-user"))
        self.assertFalse(self.store.delete_profile("demo-user"))
        reopened = MemoryStore(self.path)
        self.assertIsNone(reopened.get_profile("demo-user"))
        self.assertEqual(reopened.get_profile("other-user"), other)

    def test_delete_unknown_user_returns_false(self):
        self.assertFalse(self.store.delete_profile("missing"))

    def test_ids_are_case_sensitive(self):
        self.store.save_profile(self.profile)
        self.assertIsNone(self.store.get_profile("DEMO-USER"))

    def test_unicode_and_sql_characters_round_trip_as_data(self):
        special = UserProfile(
            user_id="x'; DROP TABLE profiles; --", current_skills=["हिन्दी", "C#", "O'Reilly"],
            career_goal="Learn SQL; don't execute this text",
        )
        self.store.save_profile(self.profile)
        self.store.save_profile(special)
        self.assertEqual(self.store.get_profile(special.user_id), special)
        self.assertEqual(self.store.get_profile("demo-user"), self.profile)
        self.assertTrue(self.store.delete_profile(special.user_id))
        self.assertEqual(self.store.get_profile("demo-user"), self.profile)

    def test_invalid_ids_are_rejected_at_all_entry_points(self):
        for user_id in ("", " ", " padded", "padded ", "x" * 129, "a\x00b", 123, None):
            with self.subTest(user_id=user_id):
                with self.assertRaises((ValueError, ValidationError)):
                    UserProfile(user_id=user_id)
                with self.assertRaises(ValueError):
                    self.store.get_profile(user_id)
                with self.assertRaises(ValueError):
                    self.store.delete_profile(user_id)

    def test_invalid_skills_are_rejected(self):
        for skills in ([""], [" "], [7], ["a\x00b"], ["x" * 101], ["Kotlin"] * 51, "Kotlin"):
            with self.subTest(skills=skills):
                with self.assertRaises(ValidationError):
                    UserProfile(user_id="demo-user", current_skills=skills)

    def test_invalid_goals_are_rejected(self):
        for goal in ("", " ", 7, "x" * 1001, "a\x00b"):
            with self.subTest(goal=goal):
                with self.assertRaises(ValidationError):
                    UserProfile(user_id="demo-user", career_goal=goal)

    def test_unknown_fields_are_rejected(self):
        with self.assertRaises(ValidationError):
            UserProfile(user_id="demo-user", inferred_proficiency="expert")

    def test_unknown_and_explicitly_empty_skills_stay_distinct(self):
        self.store.save_profile(UserProfile(user_id="unknown", career_goal="Learn Android"))
        self.store.save_profile(UserProfile(user_id="beginner", current_skills=[]))
        reopened = MemoryStore(self.path)
        self.assertIsNone(reopened.get_profile("unknown").current_skills)
        self.assertEqual(reopened.get_profile("beginner").current_skills, ())

    def test_skill_limits_and_normalization_match_comparison_tool(self):
        from careerpilot.tools import CompareSkillsInput

        skills = ["  Kotlin  "] + ["x" * 100] * 49
        profile = UserProfile(user_id="demo-user", current_skills=skills)
        arguments = CompareSkillsInput(current_skills=list(profile.current_skills), required_skills=["Kotlin"])
        self.store.save_profile(profile)
        self.assertEqual(list(self.store.get_profile("demo-user").current_skills), arguments.current_skills)

    def test_step1_profile_json_remains_readable(self):
        self.store.save_profile(self.profile)
        self.replace_payload('{"user_id":"demo-user","current_skills":[],"career_goal":null}')
        self.assertEqual(self.store.get_profile("demo-user").current_skills, ())

    def test_profile_is_an_immutable_snapshot(self):
        skills = ["Kotlin"]
        profile = UserProfile(user_id="demo-user", current_skills=skills)
        skills.append("Java")
        self.assertEqual(profile.current_skills, ("Kotlin",))
        with self.assertRaises(ValidationError):
            profile.career_goal = "changed"

    def test_save_revalidates_unchecked_model_copy(self):
        self.store.save_profile(self.profile)
        invalid = self.profile.model_copy(update={"current_skills": ("",)})
        with self.assertRaises(ValidationError):
            self.store.save_profile(invalid)
        self.assertEqual(self.store.get_profile("demo-user"), self.profile)

    def test_save_requires_profile_instance(self):
        with self.assertRaises(TypeError):
            self.store.save_profile({"user_id": "demo-user"})

    def test_corrupt_json_is_rejected_without_echoing_content(self):
        self.store.save_profile(self.profile)
        self.replace_payload("private invalid payload")
        with self.assertRaises(MemoryDataError) as error:
            self.store.get_profile("demo-user")
        self.assertNotIn("private invalid payload", str(error.exception))

    def test_invalid_stored_profile_is_rejected(self):
        self.store.save_profile(self.profile)
        self.replace_payload('{"user_id":"demo-user","current_skills":[42]}')
        with self.assertRaises(MemoryDataError):
            self.store.get_profile("demo-user")

    def test_stored_identity_mismatch_is_rejected(self):
        self.store.save_profile(self.profile)
        self.replace_payload(UserProfile(user_id="other-user").model_dump_json())
        with self.assertRaises(MemoryDataError):
            self.store.get_profile("demo-user")

    def test_future_schema_version_is_rejected_without_resetting(self):
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute("PRAGMA user_version = 99")
        with self.assertRaises(MemoryDataError):
            MemoryStore(self.path)
        with closing(sqlite3.connect(self.path)) as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 99)

    def test_path_stays_stable_after_working_directory_change(self):
        previous = Path.cwd()
        try:
            os.chdir(self.temporary.name)
            store = MemoryStore(Path("relative") / "memory.sqlite3")
        finally:
            os.chdir(previous)
        store.save_profile(self.profile)
        self.assertEqual(store.get_profile("demo-user"), self.profile)

    def test_empty_or_in_memory_path_is_rejected(self):
        for path in ("", " ", ":memory:"):
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    MemoryStore(path)


if __name__ == "__main__":
    unittest.main()
