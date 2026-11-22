# Supabase cut-over runbook

ROADGUARD AI runs on PostgreSQL 16 + PostGIS. Supabase is the supported managed target.
The bundled PostGIS container remains the offline/dev fallback and keeps working unchanged.

**Status:** the entire cut-over has been executed and verified against a **local
Supabase-shaped instance** — Supabase's role model, `extensions` schema, TLS-only
connections, and a transaction pooler on port 6543. What has *not* happened is connecting
to a hosted project, because that needs your project's DSN. Everything else is done.

Evidence with raw command output: `docs/SUPABASE_VERIFICATION.md`.
Recreate the instance yourself: `docker compose -f docker-compose.supabase.yml up -d`.

---

## 1. Which URL goes where

| Variable | Connection | Port | Used by |
| --- | --- | --- | --- |
| `SUPABASE_DB_URL` | Direct or session pooler, TLS required | 5432 | The setup script, Alembic, seeding, `demo_smoke.py` |
| `DATABASE_MIGRATION_URL` | Same as above | 5432 | Alembic, `seed_database.py`, privileged lookups |
| `SUPABASE_POOLER_URL` / `DATABASE_APP_URL` | **Transaction pooler**, TLS required | 6543 | API and worker at runtime |
| `COMPOSE_DATABASE_MIGRATION_URL` | Container view of the direct URL | 5432 | `api`/`worker` containers |
| `COMPOSE_DATABASE_APP_URL` | Container view of the pooler URL | 6543 | `api`/`worker` containers |

Paste the strings from **Supabase → Project → Connect**:

- *Connection pooling → Transaction* → the `…pooler.supabase.com:6543` string. This is the
  runtime URL; it may include `?pgbouncer=true`.
- *Direct connection* → `db.<ref>.supabase.co:5432`. This is the migration URL.

Never put the direct URL in the runtime slot under load: a serverless/container fleet will
exhaust Postgres connections. Never put the pooler URL in the migration slot: DDL cannot
survive transaction multiplexing (the app now refuses this explicitly).

---

## 2. Role model, and how the app maps onto it

| Supabase role | Behaviour | ROADGUARD use |
| --- | --- | --- |
| `postgres` | Owner, `BYPASSRLS` | Migrations and seeding only (`DATABASE_MIGRATION_URL`). Never the runtime role — RLS would silently stop applying. |
| `service_role` | `BYPASSRLS`, server key | Not used. Reserved for maintenance jobs that genuinely need to cross tenants. |
| `authenticated` | Client role, RLS-bound | Not used by this app; the browser never talks to Postgres. |
| `anon` | Client role, no privileges | Not used. |
| **`roadguard_app`** | LOGIN, `NOSUPERUSER NOBYPASSRLS NOINHERIT` | **The runtime role.** Conceptually the server-side equivalent of `authenticated`: every query is filtered by RLS using `app.current_organization_id`. |

`python scripts/supabase_setup.py --bootstrap` creates/hardens `roadguard_app`, grants
current **and future** objects (default privileges), sets its `search_path` to include
`extensions`, and re-revokes `UPDATE`/`DELETE`/`TRUNCATE` on `audit_logs` on every run.

---

## 3. Cut-over (the only steps left for you)

1. Create the project, wait for it to be healthy, and copy both connection strings.
2. Put them in `.env` (never in chat):

```dotenv
SUPABASE_DB_URL=postgresql://postgres:<pw>@db.<ref>.supabase.co:5432/postgres?sslmode=require
SUPABASE_POOLER_URL=postgresql://postgres.<ref>:<pw>@aws-0-<region>.pooler.supabase.com:6543/postgres?sslmode=require&pgbouncer=true
DATABASE_SSL_MODE=require
```

3. Run the whole cut-over in one command:

```bash
python scripts/supabase_setup.py \
  --url "$SUPABASE_DB_URL" \
  --app-url "$SUPABASE_POOLER_URL" \
  --bootstrap --write-env --migrate
```

   It prints a redacted URL, inspects the project, bootstraps, rewrites `.env`
   (`DATABASE_*`, `COMPOSE_DATABASE_*`), and runs `alembic upgrade head` over the direct
   connection. The app-role password is generated and never echoed.
4. Verify:

```bash
python scripts/supabase_setup.py --url "$SUPABASE_DB_URL"
python -m pytest tests/integration/test_database.py tests/integration/test_tenant_isolation.py
python scripts/demo_smoke.py --external-worker
```

   Expect `[ok]` on every inspection row, 23 RLS tables / 23 policies, and 12/12 smoke steps.
5. Point the containers at it:

```bash
docker compose up -d --build api worker web redis minio minio-init   # no postgres service
```

### SQL-Editor-only path (no Python on the project)

```text
1. infrastructure/supabase/hosted-bootstrap.sql   (extensions, role, grants, audit revoke)
2. infrastructure/supabase/schema.sql             (full schema, pins Alembic head)
3. infrastructure/supabase/verify.sql             (read-only checks)
```

Replace `CHANGE_ME_STRONG_PASSWORD` in the bootstrap first. `schema.sql` is generated from a
database migrated to head on a Supabase-shaped instance and was loaded into a fresh database
during verification (24 tables, 23 RLS tables, 23 policies, audit DML revoked).

---

## 4. Failure modes you will actually hit

| Symptom | Cause | Fix |
| --- | --- | --- |
| `Refusing to connect without TLS: … requires sslmode=require` | URL lacks TLS | Add `?sslmode=require`; the loader refuses rather than silently downgrading. |
| `invalid connection option "pgbouncer"` | Prisma-style `?pgbouncer=true` reaches libpq | Already fixed: the loader reads and strips it. If you see this on an old build, upgrade. |
| `prepared statement "_pg3_0" already exists` | Automatic prepared statements through the transaction pooler | Already fixed: port 6543 or `pgbouncer=true` sets `prepare_threshold=None`. |
| `Migrations must use a direct/session connection` | Pooler URL in `DATABASE_MIGRATION_URL` | Use the 5432 string for migrations; keep 6543 for runtime. |
| `pgbouncer=true was set on a non-pooler URL (port 5432)` | Flag on a direct URL | Remove the flag or use the pooler. |
| `server login has been failing, try again later` after rotating the app password | pgbouncer caches the failed server login | Re-run bootstrap with the same `--app-password`, then restart/reload the pooler (or wait ~15 s). |
| `remaining connection slots are reserved` | Too many direct connections | Use the pooler for runtime; lower `DATABASE_POOL_SIZE`. |
| RLS "works" but tenants see everything | Using `postgres` at runtime | Use `roadguard_app`; `postgres` has `BYPASSRLS`. |

---

## 5. Local Supabase-shaped verification stack

```bash
docker compose -f docker-compose.supabase.yml up -d     # 5433 direct, 6543 pooler
```

- `postgis/postgis:16-3.4`, database `postgres`, superuser `postgres`.
- `anon`, `authenticated` (NOLOGIN), `service_role` (BYPASSRLS, NOLOGIN), `authenticator`
  (LOGIN NOINHERIT), and `roadguard_app` (LOGIN, NOBYPASSRLS, NOINHERIT, member of
  `authenticated`).
- PostGIS + pgcrypto in an `extensions` schema; database `search_path` includes it.
- TLS on with a generated certificate; `pg_hba` **rejects non-TLS TCP**.
- pgbouncer in `transaction` mode on 6543, TLS on both legs.

Local-only passwords are `postgres` and `roadguard_app_local_only`; certificates live in a
Docker volume. Nothing here is used on a hosted project.

What this stack does **not** reproduce: Supavisor's exact protocol handling, connection
limits by plan, PITR/backups, the Supabase dashboard/Auth/Storage APIs, or the project's
network path. Those are the residual risks that only your DSN can retire.

---

## 6. What was proven locally (short form)

| Check | Result |
| --- | --- |
| TLS required, plaintext rejected | `ssl=True`; `sslmode=disable` → `pg_hba.conf rejects connection` |
| Roles | `anon`/`authenticated` NOLOGIN, `service_role` BYPASSRLS, `roadguard_app` login + no bypass |
| Migrations from empty | 3 revisions → `837c7ef69730 (head)`, 0 errors |
| Idempotent re-run | second `upgrade head` → no upgrade lines, exit 0 |
| Schema | 24 tables, 23 RLS tables, 23 policies (all referencing `current_organization_id`), 60 FKs, 119 indexes, 2 functions, 1 trigger, 4 geography columns |
| Audit immutability | `UPDATE`/`DELETE` denied to `roadguard_app`; `SELECT`/`INSERT` allowed |
| Cross-tenant reads | org A sees 3 own cameras, 0 of org B, 0 with no tenant context |
| Cross-tenant write | `new row violates row-level security policy`, 0 rows persisted |
| Isolation suite through pooler | 18 passed, 0 skipped, exit 0 |
| External-worker workflow | 12/12 steps, `OK: full workflow completed end to end.` |
| SQL-only path | fresh database → 24 tables, 23 policies, head pinned, audit DML revoked |
| Unsafe URL combos | all refused with actionable messages |
