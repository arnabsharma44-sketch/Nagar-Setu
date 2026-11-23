# ROADGUARD AI — Project Audit

Date: 2026-11-22
Commit state: uncommitted working tree on `main` (19 modified, 9 untracked at audit start).
Environment: Windows host, Docker Desktop, `postgres`/`redis`/`minio`/`api`/`worker`/`web` running,
API `live=200 ready=200`, Alembic `837c7ef69730 (head)`.

## Method

Nothing below is inferred from the presence of a file or an HTTP 200. Each claim maps to a
command, a database query or a browser action; the reports in this directory carry the raw
output. Where a check could not run, the status is **BLOCKED** and the reason is stated.

Inspection order:

1. Repository and documentation inventory; `git status` preserved (no resets, no discards).
2. Frontend route inventory from the filesystem, then a production build, then browser checks.
3. FastAPI router/service/model/migration inspection and the OpenAPI surface.
4. Worker and AI-engine inspection.
5. Database queries for structure, constraints, RLS and integrity.
6. Dataset source probes against the official URLs.
7. End-to-end workflow through the real containers.

## What the system actually is

| Area | Reality |
| --- | --- |
| Frontend | Next.js App Router, 23 pages (3 dynamic), two themes: dark command centre and light admin portal. No route handlers; the web container proxies `/api/*` to FastAPI. |
| Backend | FastAPI, 82 documented operations across 69 paths; cookie session + CSRF; organisation-scoped RBAC. |
| Database | PostgreSQL 16 + PostGIS, 25 tables, 23 with RLS and a policy each, 60 foreign keys, all validated. |
| Worker | Celery task plus an in-process polling runner; jobs are leased, attempt-counted and retry-safe. |
| AI | Deterministic synthetic-scene detector (demo), optional YOLO adapter, IoU/ByteTrack-style tracking, six rule evaluators, evidence rendering. |
| Storage | Local filesystem backend or MinIO; evidence is served through short-lived signed tokens, never public paths. |
| Datasets | **None acquired.** All three official sources are blocked to automated access; see §5. |

## Verified working (executed this audit)

- 12/12 containerised workflow steps: upload → job → detection → candidate event → review →
  investigation → asset/department/contract match → recommendation → approval → work order →
  completion evidence → independent verification → audit trail (`scripts/demo_smoke.py`).
- 23-page production build compiles; TypeScript passes.
- Login, command dashboard, admin portal and a dynamic work-order detail page render real
  database content in Chromium with no console errors after load.
- RBAC: auditor/engineer are denied privileged reads (403) and an auditor write with a valid body
  is denied 403 with no row created.
- Database integrity: zero orphan rows across eight cross-table checks, zero cross-tenant
  mismatches, zero duplicate incidents per job/type, audit rows immutable to the runtime role.
- 82/69 endpoint coverage suite passes; anonymous sweep rejects everything except the five
  declared pre-auth operations.

## Known defects and gaps

| ID | Severity | Status |
| --- | --- | --- |
| B-002 | P2 | **FIXED** — dashboard "Cameras online" counted `is_enabled` instead of `connection_status`, reporting 13/13 online when 0 were online. |
| B-001 | P3 | **FIXED** — dataset helper printed the archive stem as the `--dataset` argument. |
| B-003 | P3 | Open — body validation (422) precedes RBAC (403) on some writes; no state change, minor detail disclosure. |
| B-004 | P3 | Observation — one unreproducible 401 for a valid password, followed by six consecutive 200s. No lockout code path exists. |

Full detail: `BUG_REGISTER.md`.

## Not verified (explicit)

- Real-world detection quality: no labelled dataset acquired, YOLO weights absent.
- Real RTSP CCTV: no authorised feed; the simulated replay path is labelled as such in the UI.
- Road-damage detection: **not implemented** — no model, and none is faked.
- Automated accessibility (axe) and the Playwright viewport matrix: tooling not installed.
- Live Supabase: credentials and endpoints configured in `.env`; schema and bootstrap scripts ready for deployment.

## Verdict

The vertical slice is demonstrable end to end on synthetic data with honest labelling.
It is **not** evidence of real-world accident-detection accuracy, and the reports say so on
every relevant page.
