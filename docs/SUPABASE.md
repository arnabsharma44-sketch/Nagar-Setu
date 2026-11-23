# Supabase runbook

ROADGUARD AI runs on PostgreSQL 16 + PostGIS. Supabase is the supported managed target;
the bundled PostGIS container remains the offline/dev fallback.

**Two different claims, kept apart:**

- **Proven locally, from erased containers and volumes:** the full switch — TLS, Supabase's
  role model, migrations empty→head, RLS tenant isolation through a transaction pooler,
  append-only audit, the 12-step workflow, and the SQL-only path.
- **Unverified, pending your DSN:** everything that only a real hosted project can show —
  Supavisor behaviour, plan connection limits, the network path, backups/PITR.

Evidence, with the actual cold-start transcript: `docs/SUPABASE_VERIFICATION.md`.

---

## 1. Which URL goes where

| Variable | Connection | Port | Used by |
| --- | --- | --- | --- |
| `SUPABASE_DB_URL` | Direct or session pooler, TLS required | 5432 | Setup script, Alembic, seeding, smoke |
| `DATABASE_MIGRATION_URL` | Same as above | 5432 | Alembic, `seed_database.py` |
| `SUPABASE_POOLER_URL` / `DATABASE_APP_URL` | **Transaction pooler**, TLS required | 6543 | API and worker at runtime |
| `COMPOSE_DATABASE_MIGRATION_URL` | Container view of the direct URL | 5432 | `api`/`worker` containers |
| `COMPOSE_DATABASE_APP_URL` | Container view of the pooler URL | 6543 | `api`/`worker` containers |

From **Supabase → Project → Connect**:

- *Connection pooling → Transaction*: `…pooler.supabase.com:6543`, may include
  `?pgbouncer=true`. **Runtime only.**
- *Direct connection*: `db.<ref>.supabase.co:5432`. **Migrations only.**

Never invert them: the pooler cannot hold DDL across statements (the app now refuses), and
the direct URL under a container fleet exhausts Postgres connections.

---

## 2. Cold start, local Supabase-shaped stack (proven)

Requires Docker and the project virtualenv. This destroys **only** the `roadguard-supabase`
project's containers and volumes; the dev stack (`docker-compose.yml`) is untouched.

```bash
docker compose -f docker-compose.supabase.yml down -v
bash scripts/verify_supabase_coldstart.sh
```

That is the whole procedure — no manual fixes, no reordering. The script performs, in order:

1. `down -v` plus removal of leftover containers and local runtime storage.
2. `up -d`, then waits for database health (the `certs` one-shot must finish before the
   pooler starts; Compose's `service_completed_successfully` enforces that).
3. Proves TLS is required (a `sslmode=disable` attempt is refused) and that the Supabase role
   set exists: `anon`/`authenticated` NOLOGIN, `service_role` BYPASSRLS, `roadguard_app`
   LOGIN without superuser/BYPASSRLS.
4. Bootstraps the runtime role over the **direct** URL with a fixed local app password that
   matches the pooler's userlist.
5. Migrates empty → head over the direct URL.
6. Runs Alembic a second time and **fails if any migration reapplies**.
7. Prints the schema/RLS/audit facts from the database.
8. Seeds both demo organisations, including one full workflow graph (incident, evidence,
   video, job, investigation, work order) so the isolation suite cannot skip.
9. Runs `test_database.py` + `test_tenant_isolation.py` through the pooler with a JUnit
   assertion that **skipped = 0**.
10. Starts the API on the pooler URL, then a **separate external worker**, and runs the
    12-step workflow.
11. Re-runs bootstrap *without* a password and then logs in through the pooler — the
    stale-credential regression check.
12. Loads `infrastructure/supabase/schema.sql` into a brand-new database and checks it.

Success ends with `=== COLD START PASS ===` and leaves the stack running:

| Endpoint | Value |
| --- | --- |
| Direct Postgres | `127.0.0.1:5433`, user `postgres`, TLS required |
| Transaction pooler | `127.0.0.1:6543`, user `roadguard_app`, TLS required |
| App runtime URL | `postgresql://roadguard_app:<generated>@127.0.0.1:6543/postgres?sslmode=require&pgbouncer=true` |

The **app-role password is generated on every cold run** and written only to
`infrastructure/supabase/pgbouncer/userlist.txt`, which git ignores. No credential for the
runtime role exists in tracked files. The `postgres` superuser keeps the throwaway local
default from the compose file; both endpoints bind to localhost and must never be exposed or
reused on a hosted project. The script does not touch `.env`, so the dev path keeps its own
database.

To read the generated password when connecting by hand:

```bash
cat infrastructure/supabase/pgbouncer/userlist.txt   # ignored, local only
```

Stop it with:

```bash
docker compose -f docker-compose.supabase.yml down        # add -v to erase the data too
```

---

## 3. Cut over a hosted project (UNVERIFIED — needs your DSN)

This is the one step that cannot be executed here. Nothing below has been run against a
hosted Supabase project.

1. Create the project, wait until healthy, copy both connection strings from Connect.
2. Put them in `.env` (never in chat or a commit):

```dotenv
SUPABASE_DB_URL=postgresql://postgres:<pw>@db.<ref>.supabase.co:5432/postgres?sslmode=require
SUPABASE_POOLER_URL=postgresql://postgres.<ref>:<pw>@aws-0-<region>.pooler.supabase.com:6543/postgres?sslmode=require&pgbouncer=true
DATABASE_SSL_MODE=require
```

3. Bootstrap, write `.env`, and migrate in one command:

```bash
python scripts/supabase_setup.py \
  --url "$SUPABASE_DB_URL" \
  --app-url "$SUPABASE_POOLER_URL" \
  --bootstrap --write-env --migrate
```

   The app-role password is generated on first creation and never printed. **A later run
   without `--app-password` leaves it unchanged**, so re-running bootstrap cannot lock the
   pooler out. To rotate deliberately, pass `--app-password` and then reload/restart the
   pooler.

4. Verify:

```bash
python scripts/supabase_setup.py --url "$SUPABASE_DB_URL"
python -m pytest tests/integration/test_database.py tests/integration/test_tenant_isolation.py -rs
python scripts/demo_smoke.py --external-worker
```

   Expect every `[ok]` row, 23 RLS tables / 23 policies, zero skips, 12/12 steps.

5. Point containers at it (no local `postgres` service):

```bash
docker compose up -d --build api worker web redis minio minio-init
```

### SQL-Editor-only path (no Python on the project)

```text
1. infrastructure/supabase/hosted-bootstrap.sql   (extensions, role, grants, audit revoke)
2. infrastructure/supabase/schema.sql             (full schema, pins Alembic head)
3. infrastructure/supabase/verify.sql             (read-only checks)
```

Replace `CHANGE_ME_STRONG_PASSWORD` first. `schema.sql` is generated from a database migrated
to head and is proven locally by loading it into a fresh database.

---

## 4. Role model

| Supabase role | Behaviour | ROADGUARD use |
| --- | --- | --- |
| `postgres` | Owner, BYPASSRLS | Migrations and seeding only. Never runtime — RLS would stop applying. |
| `service_role` | BYPASSRLS | Not used; reserved for cross-tenant maintenance. |
| `authenticated` | Client role, RLS-bound | Not used; the browser never talks to Postgres. |
| `anon` | No privileges | Not used. |
| **`roadguard_app`** | LOGIN, NOSUPERUSER, NOBYPASSRLS, NOINHERIT | **Runtime role.** Queries are filtered by RLS on `app.current_organization_id`. |

`--bootstrap` creates/hardens `roadguard_app`, grants current and future objects, extends
`search_path` with `extensions`, and re-revokes `UPDATE`/`DELETE`/`TRUNCATE` on `audit_logs`
on every run.

---

## 5. Failure modes

| Symptom | Cause | Fix |
| --- | --- | --- |
| `Refusing to connect without TLS` | URL lacks TLS | Add `?sslmode=require`. |
| `invalid connection option "pgbouncer"` | `?pgbouncer=true` reached libpq | Already fixed (stripped before libpq). |
| `prepared statement "_pg3_0" already exists` | Auto-prepared statements on the transaction pooler | Already fixed (`prepare_threshold=None` on 6543). |
| `Migrations must use a direct/session connection` | Pooler URL in the migration slot | Use 5432 for Alembic. |
| `pgbouncer=true was set on a non-pooler URL` | Flag on a 5432 URL | Remove it or use the pooler. |
| `server login has been failing, try again later` | Password rotated out-of-band into a live pooler | Reload/restart the pooler, or wait ~15 s. Bootstrap no longer rotates on re-run. |
| `remaining connection slots are reserved` | Too many direct connections | Runtime uses the pooler; lower `DATABASE_POOL_SIZE`. |
| Tenants see everything | Runtime uses `postgres` | Use `roadguard_app`; `postgres` bypasses RLS. |

---

## 6. Scope of the proof

Reproduced locally: Supabase role names and attributes, `extensions` schema, TLS
enforcement, transaction pooling with prepared-statement behaviour, RLS through the pooler,
append-only audit, migration idempotency, and the SQL-only install.

Not reproducible without a hosted project: **Supavisor** (the local stack uses pgbouncer),
plan connection limits, actual network latency/firewall behaviour, and backups/PITR.
