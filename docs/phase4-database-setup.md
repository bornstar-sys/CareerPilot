# Phase 4 Step 3A: PostgreSQL and pgvector setup

This guide configures the local development database. Docker startup, the
vector extension, Python TCP connectivity and the subsequent vector-store
integration tests have been verified on Windows. The original pre-database
checkpoint was 187 tests and 200 subtests; see progress.md for current results.

## Files

Copy infra/postgres and this documentation file into the matching directories
under D:\Projects\CareerPilot. Preserve the .gitignore file included in the ZIP.
No existing application files, backend/.env, or dependency pins are replaced.

The Compose service uses pgvector/pgvector:0.8.7-pg17-trixie, published by the
pgvector project. PostgreSQL 17's data directory is /var/lib/postgresql/data.
The image tag fixes the PostgreSQL major and pgvector release; it is not a
content digest pin for the underlying image.

| Setting | Value |
| --- | --- |
| Compose project | careerpilot-rag |
| Service | postgres |
| Database | careerpilot |
| Local development bootstrap user | careerpilot |
| Host address | 127.0.0.1 |
| Windows host port | 5433 |
| Container port | 5432 |
| Data volume | careerpilot-rag_postgres_data |
| Password file | infra/postgres/.env, excluded by the included .gitignore |

The POSTGRES_USER account is the development bootstrap superuser. A separate
restricted application role and authentication design are future work before
external deployment. This configuration is for local development.

## 1. Generate a local password

Run from the repository root in PowerShell. The password stays on your computer
and is not printed. Rerunning this keeps an existing configuration.

```powershell
cd D:\Projects\CareerPilot

@'
from pathlib import Path
import secrets

path = Path("infra/postgres/.env")
try:
    with path.open("x", encoding="utf-8") as stream:
        stream.write("CAREERPILOT_POSTGRES_PASSWORD=" + secrets.token_hex(24) + "\n")
    print("Local database settings created.")
except FileExistsError:
    print("Keeping existing local database settings.")
'@ | .\backend\.venv\Scripts\python.exe -

git check-ignore infra/postgres/.env
```

The last command should print infra/postgres/.env. If it does not, check that
infra/postgres/.gitignore was copied before making any Git commit. Do not paste
the password file or expanded Compose configuration into chat.

## 2. Start the database

Keep Docker Desktop running. Use the same repository-root working directory.

```powershell
docker compose --env-file infra/postgres/.env -f infra/postgres/compose.yaml config --quiet
docker compose --env-file infra/postgres/.env -f infra/postgres/compose.yaml up -d --wait --wait-timeout 120
docker compose --env-file infra/postgres/.env -f infra/postgres/compose.yaml ps
```

The first command checks the configuration without printing the resolved
password. The second downloads the image if needed and waits for a healthy
database. The named volume persists database files across container restarts.
The init SQL enables vector on the first startup of an empty volume. Its scripts
do not rerun when an already initialized volume is reused.

The health check uses TCP so it does not report healthy during the temporary
Unix-socket-only initialization server. Host port 5433 is bound to localhost.

## 3. Verify the database and extension

```powershell
docker compose --env-file infra/postgres/.env -f infra/postgres/compose.yaml exec -T postgres psql -U careerpilot -d careerpilot -v ON_ERROR_STOP=1 -c "SELECT current_database(), current_user; SELECT extversion AS pgvector_version FROM pg_extension WHERE extname = 'vector'; SELECT vector_dims(array_fill(0::real, ARRAY[384])::vector(384)) AS embedding_dimensions; SELECT 1 - ('[1,0,0]'::vector <=> '[1,0,0]'::vector) AS cosine_similarity;"
```

Expected values: careerpilot, careerpilot, pgvector version 0.8.7,
embedding_dimensions 384, cosine_similarity 1. The last two queries check
384-dimensional storage type support and cosine distance arithmetic. They do
not create application tables or exercise retrieval over real document chunks.

This psql command connects inside the container through its local socket. It
does not prove that the Windows Python application can authenticate over TCP.
The subsequent Python adapter check passed on Windows using host 127.0.0.1
and port 5433; all 11 PostgreSQL integration tests also passed.

## Normal shutdown and resume

Stop the database without deleting its data:

```powershell
docker compose --env-file infra/postgres/.env -f infra/postgres/compose.yaml stop
```

After reopening Docker Desktop, resume with the same up command above.
Do not use down --volumes or delete the named volume to fix connection problems:
those actions remove the database data. Persistent storage is not a backup.

Changing POSTGRES_PASSWORD in .env does not change the password of a database
already initialized on disk. Keep the generated file; later password rotation
requires a database change too. Do not recreate credentials on each startup.

## If startup fails

Inspect the service logs without changing or deleting the volume:

```powershell
docker compose --env-file infra/postgres/.env -f infra/postgres/compose.yaml logs --tail 80 postgres
```

If port 5433 is occupied, report the error so the host port and future Python
connection settings can be adjusted together. If the vector query returns no
row, report it: an existing volume may have skipped first-run initialization.

## Validation and related components

The image tag, YAML, port mapping, volume path and initialization file were
checked during preparation. The user then verified a healthy Windows Docker
container, database careerpilot and vector extension 0.8.7. Python TCP
authentication passed, with vector dimensions 384 and self similarity 1.0.

The PostgreSQL adapter, embedding-space identity, transactional document
storage and scoped retrieval are implemented; all 11 native database tests
passed. Real indexing and a separate query-only process also passed. See
phase4-vector-store.md and phase4-grounded-answers.md for usage and evidence.
Git publication remains a separate checkpoint recorded in progress.md.

Sources:
- https://hub.docker.com/r/pgvector/pgvector/tags
- https://hub.docker.com/_/postgres
- https://github.com/pgvector/pgvector
- https://docs.docker.com/reference/compose-file/services/
