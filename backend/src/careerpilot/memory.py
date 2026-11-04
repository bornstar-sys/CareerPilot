"""Explicit local profile storage. This module does not call an LLM."""

from contextlib import closing
from pathlib import Path
import sqlite3
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictStr, ValidationError, field_validator

from careerpilot.tools import SkillName


def _validate_user_id(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("User ID must be a string.")
    if not value.strip() or value != value.strip() or len(value) > 128 or "\x00" in value:
        raise ValueError("User ID must be 1-128 characters without outer whitespace or NUL.")
    return value


class UserProfile(BaseModel):
    """Caller-supplied facts; None means unknown, () means explicitly no skills."""

    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)

    user_id: StrictStr
    current_skills: tuple[SkillName, ...] | None = Field(
        default=None, max_length=50
    )
    career_goal: Annotated[StrictStr, Field(min_length=1, max_length=1000)] | None = None

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, value: str) -> str:
        return _validate_user_id(value)

    @field_validator("current_skills")
    @classmethod
    def validate_skills(cls, value: tuple[str, ...] | None) -> tuple[str, ...] | None:
        if value is not None and any("\x00" in skill for skill in value):
            raise ValueError("Skills must contain text and cannot contain NUL.")
        return value

    @field_validator("career_goal")
    @classmethod
    def validate_goal(cls, value: str | None) -> str | None:
        if value is not None and (not value.strip() or "\x00" in value):
            raise ValueError("Career goal must contain text and cannot contain NUL.")
        return value


class MemoryDataError(RuntimeError):
    """Stored profile data failed validation; do not use it as agent input."""


class MemoryStore:
    """File-backed SQLite store with one short-lived connection per operation.

    IDs are case-sensitive lookup keys, not authentication. Save replaces the
    entire profile; None clears a field, while () means explicitly no skills. The caller
    must supply a dedicated database path and explicitly choose when to save.
    """

    def __init__(self, database_path: str | Path) -> None:
        if not str(database_path).strip() or str(database_path) == ":memory:":
            raise ValueError("Use a non-empty file path for persistent memory.")
        self._database_path = Path(database_path).expanduser().resolve()
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self._database_path, timeout=5.0)) as connection:
            with connection:
                version = connection.execute("PRAGMA user_version").fetchone()[0]
                if version not in (0, 1):
                    raise MemoryDataError("Unsupported memory schema version.")
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS profiles ("
                    "user_id TEXT PRIMARY KEY NOT NULL, "
                    "profile_json TEXT NOT NULL)"
                )
                connection.execute("PRAGMA user_version = 1")

    @property
    def database_path(self) -> Path:
        return self._database_path

    def save_profile(self, profile: UserProfile) -> UserProfile:
        """Create or fully replace a profile in one transaction."""
        if not isinstance(profile, UserProfile):
            raise TypeError("Expected a UserProfile.")
        # Revalidate even model_construct/model_copy instances before writing.
        snapshot = UserProfile.model_validate(profile.model_dump())
        with closing(sqlite3.connect(self._database_path, timeout=5.0)) as connection:
            with connection:
                connection.execute(
                    "INSERT INTO profiles (user_id, profile_json) VALUES (?, ?) "
                    "ON CONFLICT(user_id) DO UPDATE SET profile_json = excluded.profile_json",
                    (snapshot.user_id, snapshot.model_dump_json()),
                )
        return snapshot

    def get_profile(self, user_id: str) -> UserProfile | None:
        """Return a validated profile or None if this exact ID is absent."""
        user_id = _validate_user_id(user_id)
        with closing(sqlite3.connect(self._database_path, timeout=5.0)) as connection:
            row = connection.execute(
                "SELECT profile_json FROM profiles WHERE user_id = ?", (user_id,)
            ).fetchone()
        if row is None:
            return None
        try:
            profile = UserProfile.model_validate_json(row[0])
        except (ValidationError, TypeError, ValueError):
            raise MemoryDataError("Stored profile is invalid.") from None
        if profile.user_id != user_id:
            raise MemoryDataError("Stored profile identity does not match its lookup key.")
        return profile

    def delete_profile(self, user_id: str) -> bool:
        """Delete only the requested profile; return whether one existed."""
        user_id = _validate_user_id(user_id)
        with closing(sqlite3.connect(self._database_path, timeout=5.0)) as connection:
            with connection:
                cursor = connection.execute("DELETE FROM profiles WHERE user_id = ?", (user_id,))
                deleted = cursor.rowcount > 0
        return deleted
