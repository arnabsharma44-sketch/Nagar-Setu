# Supabase-shaped verification — execution record

Date: 2026-11-22. Host: Windows + Docker Desktop. Runner: project virtualenv.
Instance: `docker compose -f docker-compose.supabase.yml up -d` → `roadguard-supabase-db`
(PostGIS 16-3.4, TLS-only, port 5433) and `roadguard-supabase-pooler` (pgbouncer 1.23.1,
transaction mode, port 6543).

This file stores actual output. Nothing here is a projection.

---

## 1. TLS is enforced, not merely available

`psycopg.connect("postgresql://postgres:postgres@127.0.0.1:5433/postgres?sslmode=require")`

```
TLS require: OK user=postgres ssl=True
TLS disable: FAILED OperationalError: connection failed: ... FATAL: pg_hba.conf rejects connection
```

## 2. Supabase role model

```
role ('anon',           login=False super=False bypassrls=False inherit=False)
role ('authenticated',  login=False super=False bypassrls=False inherit=False)
role ('authenticator',  login=True  super=False bypassrls=False inherit=False)
role ('roadguard_app',  login=True  super=False bypassrls=False inherit=False)
role ('service_role',   login=False super=False bypassrls=True  inherit=False)
postgis  ('3.4.3', 'extensions')
pgcrypto ('1.3',   'extensions')
search_path ('"$user", public, extensions')
```

`SET ROLE authenticated; SELECT count(*) FROM cameras;` →
`ERROR: permission denied for table cameras` (client roles fail closed).

---

## 3. Migration: empty → head, zero errors, idempotent

Command (from `apps/api`, with `DATABASE_MIGRATION_URL` on 5433 and `DATABASE_APP_URL` on the
pooler):

```
INFO  [alembic.runtime.migration] Running upgrade  -> a0f8b507499d, initial roadguard schema
INFO  [alembic.runtime.migration] Running upgrade a0f8b507499d -> b1c2d3e4f5a6, Security layer: extensions, Row-Level Security, append-only audit, job claim.
INFO  [alembic.runtime.migration] Running upgrade b1c2d3e4f5a6 -> 837c7ef69730, coordinate columns for map serialization
MIGRATE_EXIT=0
837c7ef69730 (head)

# second run
SECOND_EXIT=0        (no "Running upgrade" lines)
```

### Resulting schema

```
public tables        24        rls tables           23
rls policies         23        policy uses org      23
foreign keys         60        unvalidated fks       0
indexes             119        functions             2
triggers              1
geography columns    public.accident_records.location, public.assets.location,
                     public.cameras.location, public.incidents.location
audit UPDATE (app)   False     audit DELETE (app)   False
audit SELECT (app)   True      audit INSERT (app)   True
app can bypass rls   False     tables w/o app grant  0
```

---

## 4. The pooler is a real transaction pooler

Connecting as `roadguard_app` to `…:6543/postgres?sslmode=require`:

```
pooler TLS: ('roadguard_app', True)
```

Automatic preparation with a commit between executions — the pattern of a request loop:

```
auto-prepare across transactions: FAILED as expected ->
  prepared statement "_pg3_0" already exists
prepare_threshold=None across transactions: OK (8 committed executions)
```

That is the failure the loader prevents by setting `prepare_threshold=None` for port 6543 or
`pgbouncer=true`.

## 5. RLS through the pooler

```
orgs: demo-city=dfad85d9…, demo-isolation=e4f967c6…

visible cameras as org A        : 3
org B rows visible as org A     : 0
org A own rows                  : 3
cameras visible with no context : 0        (fails closed)
UPDATE of an org B row as org A : rows updated: 0
INSERT of an org B row as org A : new row violates row-level security policy for table "cameras"
probe rows persisted            : 0
```

## 6. Audit immutability

```
UPDATE denied -> permission denied for table audit_logs
DELETE denied -> permission denied for table audit_logs
audit select/insert still available: (True, True)
```

## 7. Isolation suite and workflow, against this instance

```
$ pytest tests/integration/test_database.py tests/integration/test_tenant_isolation.py -q -rs
..................                                    [100%]
SB_TESTS_EXIT=0
```

18 passed, 0 skipped. (An earlier run in the same session showed 6 skips before the second
organisation's seed data existed; the final state is skip-free.)

```
$ python scripts/demo_smoke.py --api http://127.0.0.1:8001 --external-worker
1/12 sign in as operations user      role=police_admin org=demo-city
2/12 upload synthetic CCTV clip      video=1c3d6ce1… status=processing
3/12 background processing           job=ca15d6ec… model=synthetic-scene-colour-marker events=1
4/12 candidate events                near_miss_candidate score=0.436 window=3.0-9.0s
5/12 evidence artefacts              evidence=2 items, annotated frame 63211 bytes
6/12 reviewer confirms               review_status=confirmed
7/12 investigation                   case=INV-2026-0001
8/12 record match                    department=DEMO Roads and Buildings contracts=['DEMO-CON-001']
9/12 analysis                        source=deterministic hypotheses=1 missing=1
10/12 approval                       self-approval blocked, independent approval recorded
11/12 work order                     WO-2026-0001
12/12 verification                   audit entries=43 verified
OK: full workflow completed end to end.
SMOKE_EXIT=0
```

The API (`uvicorn` on 8001) and the worker (`python -m ai_engine.workers.polling_worker
--loop`) ran as separate host processes, each configured with the pooler runtime URL.

## 8. SQL-only path (no Alembic)

`schema.sql` loaded into a brand-new database with `psql -v ON_ERROR_STOP=1`:

```
PSQL_EXIT=0
tables|24
rls|23
policies|23
head|1
audit_update|0
audit_delete|0
```

## 9. Config loader refuses unsafe combinations

```
supabase direct + sslmode=disable : REFUSED -> Refusing to connect without TLS: … requires sslmode=require
pooler + sslmode=allow            : REFUSED -> Refusing to connect without TLS: … requires sslmode=require
pgbouncer=true on 5432            : REFUSED -> pgbouncer=true was set on a non-pooler URL (port 5432)…
safe pooler URL                   : accepted;
  driver URL -> postgresql+psycopg://…:6543/postgres?sslmode=require   (pgbouncer stripped)
migrations through 6543           : ValueError "Migrations must use a direct/session connection…"
```

## 10. Defect found and fixed during this verification

`?pgbouncer=true` was detected but forwarded to libpq, which rejects unknown keywords:

```
sqlalchemy.exc.ProgrammingError: (psycopg.ProgrammingError) invalid connection option "pgbouncer"
```

Fixed in `apps/api/app/db/urls.py` (`strip_driver_params`, `validate_database_url`,
`ensure_direct_for_migrations`) and applied in `session.py`, `alembic/env.py` and
`scripts/supabase_setup.py`. Regression tests live in `tests/unit/test_database_urls.py`.

A second operational trap was confirmed: after rotating the app role password, pgbouncer
reported `server login has been failing, try again later` until restarted. The runbook
documents this.
