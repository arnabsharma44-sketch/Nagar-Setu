# ROADGUARD AI — Implementation State

**Last updated:** 22 November 2026
**Branch:** `main`. The 18 November implementation work is committed; the 22 November endpoint audit,
Supabase, dataset tooling and full quality audit (`docs/quality/`) are on disk — inspect `git status`
before continuing.
**Source specifications:** `DOCUMENTATIONS/01`–`11`, `14`, `15`

This file is the resumable state of the build. Read it first in a new session, then verify the claims
against the repository and the commands recorded in §6.

---

## 1. Phase status

The phase numbering below follows `DOCUMENTATIONS/15_MASTER_LOOPING_PROMPT_AND_PHASE_CHECKLIST.md`.
The eight-digit request's "phases 1–15" map onto it one-to-one (its phase 1 = checklist phase 0).

| Checklist phase | Status | Evidence |
| --- | --- | --- |
| 0 — Repository audit and plan | COMPLETE | Documentation pack read; environment checked; state/changelog/limitations/decisions written |
| 1 — Repository and development foundation | COMPLETE | Full Compose stack runs: postgres, redis, minio, api, worker, web all healthy; health endpoints answer; ruff/pytest/tsc/build pass |
| 2 — Database, identity, tenant isolation | COMPLETE | 3 migrations, head `837c7ef69730`; Argon2 + JWT + rotating refresh; RBAC; composite tenant FKs; RLS verified; isolation tests pass |
| 3 — Domain registries and core APIs | COMPLETE | departments, contractors, assets, contracts, cameras + deterministic responsibility lookup; idempotent DEMO seed |
| 4 — Frontend design system and two shells | COMPLETE | 24 routes (dark Command Center + light Admin Portal); shared components; loading/empty/error/permission states |
| 5 — Private upload and background jobs | COMPLETE | signed upload → private S3 storage → Celery job → worker produced the incident (`job_succeeded events=1 detections=177`); polling path also verified; failure + retry paths |
| 6 — CV detection, tracking, evidence | COMPLETE for the synthetic-scene detector; YOLO adapter UNVERIFIED | 300-frame clip processed; 1 near-miss candidate; annotated frame (62 KB) + event clip (919 KB) |
| 7 — Candidate events and human review | COMPLETE | versioned rules; unsupported rules report `unavailable`; confirm/reject/needs-info; audit entries |
| 8 — GIS, accident records, hotspots | COMPLETE | PostGIS geography + mirrored lat/lng; CSV import with provenance; DBSCAN hotspots; separate source layers |
| 9 — Investigation and responsibility | COMPLETE | facts / hypotheses / missing information separated; asset + contract + date-range matching; deterministic analysis; LLM adapter off |
| 10 — Recommendations, work orders, verification | COMPLETE | self-approval rejected; server-side transition map; completion evidence; separation of duties; audit timeline |
| 11 — Live CCTV adapter and simulated live | COMPLETE (real RTSP BLOCKED by design) | RTSP adapter stub with authorization gating; simulated sessions labelled SIMULATED LIVE; API endpoint for RTSP live |
| 12 — Real-time integration and dashboard polish | COMPLETE | ticket-authenticated WebSocket; `incident.reviewed` observed end-to-end; dashboard metrics from API |
| 13 — Security, privacy, reliability | COMPLETE (residual risks in limitations) | 61 tests incl. cross-tenant 404s, RBAC denials, CSRF rejection, audit immutability at DB level |
| 14 — End-to-end QA and release candidate | COMPLETE for the local demo environment | 12-step workflow passes both bare-metal and through the container stack (`--external-worker`); UI exercised in the browser against the built web container; README + limitations written |

COMPLETE means implemented **and** checked with the commands in §6. Anything not executed is marked
BLOCKED or PARTIALLY VERIFIED rather than claimed.

## 2. Blocked / partially verified

| Item | Status | Why | What is still required |
| --- | --- | --- | --- |
| YOLO detector (`DETECTOR_BACKEND=yolo`) | BLOCKED | `torch`/`ultralytics` are multi-GB and not installed; the adapter is import-guarded and fails clearly | Install in a GPU-capable image, supply weights, re-run pipeline, record accuracy/runtime |
| Real RTSP camera | BLOCKED | Needs authorized camera access + credentials (human decision) | Allowlist a trusted source, configure secrets, verify health/timeout/shutdown |
| LLM-drafted analysis | NOT EXERCISED | `LLM_PROVIDER=none`, no key | Configure provider, validate structured output; deterministic path remains default |
| Exposure-normalised hotspot rates | NOT IMPLEMENTED | No traffic-volume dataset; inventing one would be fabrication | Ingest volume counts, compute rates; UI states rates are not exposure-adjusted |
| External datasets (AI City Track 4, RDD2022 India, BDD100K) | BLOCKED | Official sources return HTTP 403 (RDD), a Google Drive interstitial with no bytes (AI City) and a login/licence wall (BDD100K) | Save the archives to the paths in `docs/quality/DATASET_ACQUISITION_REPORT.md`, then run the `scripts/datasets/` pipeline |
| Road-damage detection model | NOT IMPLEMENTED | No damage classifier exists; emitting guesses would be fabrication | Install/obtain an RDD-compatible model, then evaluate with `scripts/datasets/evaluate_models.py` |
| Automated UI/a11y/load tests | NOT IMPLEMENTED | Playwright, axe and a load generator are not installed | Add `@axe-core/playwright` + a route sweep before any pilot |
| Hosted Supabase project | BLOCKED (needs DSN) | No project credentials; the Supabase-shaped local instance is fully verified (migrations, RLS through the pooler, audit immutability, 12/12 smoke, SQL-only path) | Paste `SUPABASE_DB_URL` + `SUPABASE_POOLER_URL`, then run `scripts/supabase_setup.py --bootstrap --write-env --migrate` |
| Supavisor / plan-specific behaviour | NOT VERIFIED | Local verification uses pgbouncer in transaction mode, not Supabase's Supavisor | Verify connection limits and pooler behaviour after the DSN is supplied |

## 3. Documentation gaps (reported, not fabricated)

`DOCUMENTATIONS/` contains `01`–`11`, `14`, `15`, `folder structure.md` and three diagrams. The
checklist also expects `12_DEMO_DATA_AND_SCENARIO.md` and `13_DECISIONS_AND_GLOSSARY.md`, which are
**absent**:

- The demo scenario is recorded in `README.md` §Demo script and implemented by
  `scripts/demo_smoke.py` + `scripts/seed_database.py`.
- Decisions actually taken are recorded in `docs/DECISIONS_AND_GLOSSARY.md`.

## 4. Architecture as built

```
apps/web (Next.js; same-origin proxy /api → :8000)
   │  cookies (short-lived access + rotating refresh) + CSRF header
   ▼
apps/api (FastAPI) ── SQLAlchemy ──► PostgreSQL 16 + PostGIS (RLS for the app role)
   │ metadata + object keys only            ▲
   │ no video decoding in a request         │ claim/lease
   ▼                                        │
private storage (local dir or S3/MinIO)   ai-engine worker
                                            (Celery via Redis, or polling worker)
```

Decisions (full list: `docs/DECISIONS_AND_GLOSSARY.md`):

- The API never processes video; it creates an idempotent job row. The worker claims jobs through
  `SECURITY DEFINER claim_ai_job(...)`, the only sanctioned cross-tenant read.
- Isolation is layered: organization context per request, composite `(id, organization_id)` foreign
  keys, transaction-local `set_config('app.current_organization_id', …, true)`, and RLS policies
  enforced for the unprivileged `roadguard_app` role.
- Storage is abstracted (`local` / `s3`); the browser receives only short-lived signed URLs.
- Detector and tracker are adapters; defaults are a real but explicitly labelled colour-marker CV
  detector over locally generated footage and a dependency-free IoU tracker.
- WebSocket frames are hints; REST is authoritative. Each connection uses a 60-second single-use
  ticket, and the organization is derived from that ticket.

## 5. Files

```
apps/api/app/core/            config, errors, security, permissions, audit, ratelimit
apps/api/app/db/              naming conventions + mixins, tenant/privileged sessions
apps/api/app/models/          identity, registry, media, incidents, workflow, enums
apps/api/app/schemas/         common envelope, domain, serializers
apps/api/app/services/        identity, registry, cameras, videos, media_validation, storage,
                              incidents, analytics, investigations, work_orders, geo, events
apps/api/app/api/v1/          13 routers + aggregator (68 documented paths)
apps/api/alembic/versions/    a0f8b507499d schema · b1c2d3e4f5a6 security layer · 837c7ef69730 coordinates
ai-engine/ai_engine/          detection/*, tracking/tracker, events/*, video/*, pipeline,
                              investigation/*, workers/{runner,polling_worker,celery_app}
apps/web/app/                 login + /command/** (9) + /admin/** (12) routes
apps/web/components/          AppShell, UI primitives, MapPanel/MapInner, EvidenceGrid
apps/web/lib/                 api client, session context, useApi, realtime, format, types
infrastructure/docker/        api.Dockerfile, worker.Dockerfile, web.Dockerfile
infrastructure/postgres/      init.sh (extensions + unprivileged application role)
scripts/                      generate_demo_clip, seed_database, demo_smoke
tests/unit, tests/integration 61 pytest tests
shared/schemas/               realtime_event.schema.json
docs/                         this file, changelog, limitations, decisions
```

## 6. Commands executed and observed results

| Command | Result |
| --- | --- |
| `docker compose up -d postgres redis minio minio-init` | all healthy; private bucket `roadguard-private` created |
| `(cd apps/api && python -m alembic upgrade head)` | 3 revisions applied; `alembic current` reports `837c7ef69730 (head)` on host and inside the API container. `alembic.ini` uses relative paths, so this must run from `apps/api`. |
| `python scripts/seed_database.py` | idempotent; 2 orgs, 3 departments, 6 assets, 2 contractors, 2 contracts, 4 cameras, 8 accident records, 6 users |
| `python scripts/generate_demo_clip.py` | 800×450, 25 fps, 12 s, 300 frames (750 051 bytes) |
| `python -m ai_engine.workers.polling_worker --once` | job `succeeded`; 1 `near_miss_candidate` (score 0.436, window 3.0–9.0 s) |
| `python scripts/demo_smoke.py` | `OK: full workflow completed end to end.` (12/12 steps, 100 audit entries) |
| `python -m pytest` | **61 passed** (38 unit + 23 integration), 3 third-party deprecation warnings |
| `python -m ruff check apps/api ai-engine scripts tests` | `All checks passed!` |
| `npx tsc --noEmit` (apps/web) | no errors |
| `npx next build` (apps/web) | success, 24 routes emitted |
| S3 probe against MinIO (`put/stat/read/checksum/presigned GET+PUT/delete`) | all succeeded |
| WebSocket probe (ticket → connect → review incident) | `connected`, then `incident.reviewed` received |
| Browser check, dev server (`ops@demo.roadguard.ai`) | login → `/command`: 2 pending / 3 confirmed / 8 historical, 3/3 cameras, Leaflet map + event list from the API |
| `docker compose build api worker web` | all three images built |
| `docker compose up -d` (postgres, redis, minio, minio-init, api, worker, web) | every service healthy / running; bucket created |
| `python scripts/demo_smoke.py --external-worker` against the container stack | `OK: full workflow completed end to end.` — Celery worker logged `job_succeeded events=1 detections=177`; evidence downloaded through a MinIO presigned URL |
| Browser check, production web container → `/api` proxy → API container | `/command` rendered 1 pending candidate, 3/3 cameras, event list, and realtime status “Connected (ticket-authenticated)” |

Not executed: real RTSP, YOLO inference, LLM calls, systematic visual review of every page at
multiple viewports, browser-level automated tests, dependency/container vulnerability scans.

## 7. Outstanding bugs, risks, security notes

- No known failing test.
- `next dev` prints a Turbopack "filesystem settling" notice after a production build writes into
  `.next`; restarting the dev server clears it (cosmetic).
- Starlette deprecation warnings for `HTTP_422_UNPROCESSABLE_ENTITY` and
  `HTTP_413_REQUEST_ENTITY_TOO_LARGE` in `apps/api/app/core/errors.py` (cosmetic upstream rename).
- The login rate limiter is in-process; multi-replica deployments must move it to Redis.
- Pipeline evidence is synthetic demo imagery and must never be presented as evidential photography.

## 8. Endpoint audit, Supabase and dataset intake (22 November 2026)

- **Every documented operation is executed.** `tests/integration/test_endpoint_coverage.py` walks the
  real dependency chain and then diffs its own calls against `app.openapi()`. It fails if a documented
  operation was never called, or if any call returned 5xx. The generated matrix is
  `docs/ENDPOINT_AUDIT.md`: **82 operations across 69 paths** (the WebSocket is separate).
- **Auth sweep.** A second test replays every operation with no session and fails on any 2xx outside
  the five intentional pre-auth operations (health probes, static permission catalogue, CSRF
  bootstrap cookie, idempotent logout).
- **Supabase is supported, not yet live-verified.** `app/db/urls.py` normalises Supabase URLs, injects
  TLS and disables named prepared statements behind the 6543 pooler; Alembic escapes `%` in generated
  passwords; `scripts/supabase_setup.py` provisions/verifies extensions, the unprivileged
  `roadguard_app` role, `search_path`, grants and the append-only audit revoke, writes `.env` and can
  run migrations. Compose reads `COMPOSE_DATABASE_*_URL`. Runbook: `docs/SUPABASE.md`. The inspector
  reports `[ok]` on every row against the bundled PostGIS container; **no Supabase project was
  available in this environment**, so the live switch is the one outstanding step.
- **Dataset intake.** `docs/DATASETS.md` records the public corpora and the finding that no open
  Indian municipal fixed-CCTV accident corpus exists. `scripts/prepare_dataset.py` probes, hashes,
  validates and optionally ingests operator footage through the normal upload flow.
- **Test pack repaired.** Missing `db_engine` fixture, a class-scoped fixture, bare `Mock()` sessions,
  a mangled test function and three incorrect rule scenarios were fixed; assertions were corrected to
  the real contracts (204 for password change/logout, 415 for unsupported media, `pending → assigned →
  in_progress`). The full suite passes and `ruff` is clean.

## 9. Next tasks (priority order)

1. Add a browser-level test (Playwright) for review → investigation → work order.
2. Validate the YOLO adapter in a GPU image and record accuracy/runtime; keep `synthetic_scene`
   as the default until then.
3. Add exposure data before describing hotspot output as a risk rate.
4. Write and rehearse the retention/deletion policy and backup/restore for private evidence.
5. Run a dependency/container vulnerability scan and record the residual-risk register.
