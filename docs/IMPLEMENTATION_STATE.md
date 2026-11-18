# ROADGUARD AI — Implementation State

**Last updated:** 18 November 2026
**Branch:** `main` (single commit `3a29f34 first commit`; all implementation work is uncommitted on
disk — inspect `git status` before continuing)
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
| 1 — Repository and development foundation | COMPLETE (API image build verified; worker/web images defined — see §2) | Compose: postgres, redis, minio healthy; API + web run locally; health endpoints; ruff/pytest/tsc/build |
| 2 — Database, identity, tenant isolation | COMPLETE | 3 migrations, head `837c7ef69730`; Argon2 + JWT + rotating refresh; RBAC; composite tenant FKs; RLS verified; isolation tests pass |
| 3 — Domain registries and core APIs | COMPLETE | departments, contractors, assets, contracts, cameras + deterministic responsibility lookup; idempotent DEMO seed |
| 4 — Frontend design system and two shells | COMPLETE | 24 routes (dark Command Center + light Admin Portal); shared components; loading/empty/error/permission states |
| 5 — Private upload and background jobs | COMPLETE | signed upload → private storage → job claim/lease → worker; failure + retry paths; S3 backend verified against MinIO |
| 6 — CV detection, tracking, evidence | COMPLETE for the synthetic-scene detector; YOLO adapter UNVERIFIED | 300-frame clip processed; 1 near-miss candidate; annotated frame (62 KB) + event clip (919 KB) |
| 7 — Candidate events and human review | COMPLETE | versioned rules; unsupported rules report `unavailable`; confirm/reject/needs-info; audit entries |
| 8 — GIS, accident records, hotspots | COMPLETE | PostGIS geography + mirrored lat/lng; CSV import with provenance; DBSCAN hotspots; separate source layers |
| 9 — Investigation and responsibility | COMPLETE | facts / hypotheses / missing information separated; asset + contract + date-range matching; deterministic analysis; LLM adapter off |
| 10 — Recommendations, work orders, verification | COMPLETE | self-approval rejected; server-side transition map; completion evidence; separation of duties; audit timeline |
| 11 — Live CCTV adapter and simulated live | PARTIALLY VERIFIED (real RTSP BLOCKED) | adapter refuses to fake a connection; simulated sessions labelled SIMULATED LIVE |
| 12 — Real-time integration and dashboard polish | COMPLETE | ticket-authenticated WebSocket; `incident.reviewed` observed end-to-end; dashboard metrics from API |
| 13 — Security, privacy, reliability | COMPLETE (residual risks in limitations) | 61 tests incl. cross-tenant 404s, RBAC denials, CSRF rejection, audit immutability at DB level |
| 14 — End-to-end QA and release candidate | COMPLETE for the local demo environment | 12-step HTTP workflow passes; UI exercised in the browser; README + limitations written |

COMPLETE means implemented **and** checked with the commands in §6. Anything not executed is marked
BLOCKED or PARTIALLY VERIFIED rather than claimed.

## 2. Blocked / partially verified

| Item | Status | Why | What is still required |
| --- | --- | --- | --- |
| YOLO detector (`DETECTOR_BACKEND=yolo`) | BLOCKED | `torch`/`ultralytics` are multi-GB and not installed; the adapter is import-guarded and fails clearly | Install in a GPU-capable image, supply weights, re-run pipeline, record accuracy/runtime |
| Real RTSP camera | BLOCKED | Needs authorized camera access + credentials (human decision) | Allowlist a trusted source, configure secrets, verify health/timeout/shutdown |
| LLM-drafted analysis | NOT EXERCISED | `LLM_PROVIDER=none`, no key | Configure provider, validate structured output; deterministic path remains default |
| Worker and web container images | DEFINED, NOT BUILT | Time/bandwidth in this session; API image build was executed | `docker compose build worker web`, `docker compose up -d`, re-run smoke against containers |
| Exposure-normalised hotspot rates | NOT IMPLEMENTED | No traffic-volume dataset; inventing one would be fabrication | Ingest volume counts, compute rates; UI states rates are not exposure-adjusted |

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
| `python -m alembic -c apps/api/alembic.ini upgrade head` | 3 revisions applied; head `837c7ef69730` |
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
| Browser check (`ops@demo.roadguard.ai`) | login → `/command`: 2 pending / 3 confirmed / 8 historical, 3/3 cameras, Leaflet map + event list from the API |

Not executed: real RTSP, YOLO inference, LLM calls, worker/web container builds, systematic visual
review of every page at multiple viewports, browser-level automated tests.

## 7. Outstanding bugs, risks, security notes

- No known failing test.
- `next dev` prints a Turbopack "filesystem settling" notice after a production build writes into
  `.next`; restarting the dev server clears it (cosmetic).
- Starlette deprecation warnings for `HTTP_422_UNPROCESSABLE_ENTITY` and
  `HTTP_413_REQUEST_ENTITY_TOO_LARGE` in `apps/api/app/core/errors.py` (cosmetic upstream rename).
- The login rate limiter is in-process; multi-replica deployments must move it to Redis.
- Pipeline evidence is synthetic demo imagery and must never be presented as evidential photography.

## 8. Next tasks (priority order)

1. Build the worker and web images; re-run `scripts/demo_smoke.py` against the containerized API.
2. Add a browser-level test for review → investigation → work order.
3. Validate the YOLO adapter in a GPU image and record accuracy/runtime; keep `synthetic_scene`
   as the default until then.
4. Add exposure data before describing hotspot output as a risk rate.
5. Write and rehearse the retention/deletion policy and backup/restore for private evidence.
