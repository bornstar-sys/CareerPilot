"""Local PostgreSQL connection settings, separate from LLM configuration."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class DatabaseSettings:
    password: str = field(repr=False)
    host: str = "127.0.0.1"
    port: int = 5433
    database: str = "careerpilot"
    user: str = "careerpilot"

    def __post_init__(self):
        for value in (self.password, self.host, self.database, self.user):
            if not isinstance(value, str) or not value.strip() or "\x00" in value:
                raise ValueError("Database settings must contain nonblank strings without NUL.")
        if type(self.port) is not int or not 1 <= self.port <= 65535:
            raise ValueError("Database port must be an integer between 1 and 65535.")

    def connect(self):
        # Optional dependency: no connection or driver import during module import.
        import psycopg
        return psycopg.connect(
            host=self.host, port=self.port, dbname=self.database, user=self.user,
            password=self.password, connect_timeout=10,
            options="-c statement_timeout=30000 -c lock_timeout=10000",
        )


def load_database_settings(env_file: str | Path) -> DatabaseSettings:
    """Read our generated KEY=value file without changing process variables.

    Supports blank/comment lines and optional host/port/database/user settings.
    This intentionally is not a general dotenv parser: quotes, export syntax,
    interpolation, and inline comments are not supported.
    """
    allowed = {"CAREERPILOT_POSTGRES_" + name for name in
               ("PASSWORD", "HOST", "PORT", "DB", "USER")}
    values = {}
    for line in Path(env_file).read_text(encoding="utf-8-sig").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, separator, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not separator or key not in allowed or key in values or not value:
            raise ValueError("Invalid or duplicate database setting in the local settings file.")
        if value.startswith(("'", '"')):
            raise ValueError("Use unquoted values in the generated database settings file.")
        values[key] = value
    prefix = "CAREERPILOT_POSTGRES_"
    if prefix + "PASSWORD" not in values:
        raise ValueError("Database password is missing from the local settings file.")
    try:
        port = int(values.get(prefix + "PORT", "5433"))
    except ValueError:
        raise ValueError("Database port must be an integer.") from None
    return DatabaseSettings(
        password=values[prefix + "PASSWORD"],
        host=values.get(prefix + "HOST", "127.0.0.1"), port=port,
        database=values.get(prefix + "DB", "careerpilot"),
        user=values.get(prefix + "USER", "careerpilot"),
    )
