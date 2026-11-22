# Test Execution Plan

Every command below is run from the repository root on the audit host. Python is the project
virtualenv (`.venv/Scripts/python.exe`). Commands are ordered cheapest-first so a broken layer
stops the run early.

## 0. Preconditions

```bash
docker compose ps                     # postgres, redis, minio, api, worker, web up
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/health/ready   # 200
(cd apps/api && ../../.venv/Scripts/python.exe -m alembic current)                 # 837c7ef69730 (head)
```

Migrations must be run from `apps/api`; from the root Alembic cannot find `alembic.ini`.

## 1. Static checks

```bash
.venv/Scripts/python.exe -m ruff check apps/api ai-engine scripts tests
cd apps/web && npm run build
```

Latest result: ruff "All checks passed"; web build exit 0, 23 routes compiled.

## 2. Unit layer

```bash
.venv/Scripts/python.exe -m pytest tests/unit -q
```

Covers URL/pooler normalisation, password hashing, event rules (real converging and
decelerating scenarios), hotspot aggregation, responsibility matching, recommendation text,
and video validation (415/413, no job created on rejection).

## 3. Integration layer

```bash
.venv/Scripts/python.exe -m pytest tests/integration -q
```

- `test_endpoint_coverage.py` executes **all 82 operations across 69 paths** in dependency
  order, asserts every status, forbids 5xx, then diffs the called operations against
  `app.openapi()` — the test fails if a documented operation is never invoked, or an
  undocumented one is.
- A second test sweeps every operation anonymously; only health live/ready, `/meta/permissions`,
  `/auth/csrf` and `/auth/logout` may answer 2xx.
- `test_database.py` asserts RLS is enabled and the policy expression references
  `app.current_organization_id`.
- `test_tenant_isolation.py` creates two organisations and attempts cross-tenant reads/writes.
- `test_video_pipeline.py` covers rejection paths and evidence token scoping.

## 4. Full suite

```bash
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m pytest --collect-only -q | awk -F': ' '/: [0-9]+$/{s+=$2} END{print s}'
```

This configuration prints no summary line, so the collected count is the reliable number:
**157 tests**. Exit status is the pass criterion, not the printed text.

## 5. End-to-end through the containers

```bash
.venv/Scripts/python.exe scripts/demo_smoke.py --external-worker
```

Exercises the real network stack and the Celery/polling worker, not an in-process stub.
Expected: `OK: full workflow completed end to end.` with 12/12 steps.

## 6. Browser checks

Chromium (Freebuff preview) against `http://localhost:3000`:

1. `/login` — labels, demo account list, error container.
2. Sign in as `ops@demo.roadguard.ai`.
3. `/command`, `/admin`, `/admin/work-orders/{id}` directly.
4. Read console + network for errors after navigation.

Automated Playwright/axe runs are **not** part of this plan because the tooling is not
installed; see `VISUAL_REGRESSION_REPORT.md` for what that leaves unverified.

## 7. Database integrity

```bash
docker exec roadguard-postgres psql -U roadguard -d roadguard -c "\dt"
```

Then the queries in `DATABASE_INTEGRITY_REPORT.md` (RLS counts, unvalidated constraints,
orphans, cross-tenant mismatches, audit immutability). All current results are zero-violation.
