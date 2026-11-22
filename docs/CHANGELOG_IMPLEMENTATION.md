# ROADGUARD AI — Implementation Changelog

Newest first. Each entry records what changed, why, and how it was verified.

## 2026-11-22 — Supabase cut-over executed and verified locally

### Proven, not just coded
- Stood up a **Supabase-shaped** Postgres (`docker-compose.supabase.yml`): Supabase's role
  set (`anon`, `authenticated`, `service_role`, `authenticator`, plus `roadguard_app`),
  PostGIS/pgcrypto in an `extensions` schema, database `search_path`, TLS with non-TLS TCP
  rejected by `pg_hba`, and pgbouncer in **transaction mode on 6543** with TLS on both legs.
- Migrations ran from an empty database to `837c7ef69730` with zero errors; a second run was a
  no-op. Result: 24 tables, 23 RLS tables, 23 policies (all keyed on
  `current_organization_id`), 60 FKs, 119 indexes, 4 geography columns, append-only audit
  grants.
- RLS proven **through the pooler**: org A saw 3 own cameras, 0 of org B, 0 with no tenant
  context; a cross-tenant UPDATE touched 0 rows; a cross-tenant INSERT failed with
  `new row violates row-level security policy` and persisted nothing.
- Audit immutability proven as `roadguard_app`: `UPDATE`/`DELETE` denied, `SELECT`/`INSERT`
  allowed.
- Tenant-isolation + database suites passed against this instance through the pooler, and
  `demo_smoke.py --external-worker` completed 12/12 with separate API and worker processes
  using the pooler URL.
- SQL-only path: `infrastructure/supabase/hosted-bootstrap.sql`, `schema.sql` (pg_dump at
  head) and `verify.sql`; `schema.sql` loaded into a **fresh** database cleanly.

### Fixed
- **Supabase pooler URL bug:** `?pgbouncer=true` was detected but forwarded to libpq, which
  raises `invalid connection option "pgbouncer"`. Added `strip_driver_params`, applied in the
  session factory, Alembic env and setup script.
- Added `validate_database_url` (refuses TLS-less Supabase/pooler URLs and `pgbouncer=true` on
  5432) and `ensure_direct_for_migrations` (refuses migrations through 6543), wired into the
  engine, Alembic and `--migrate`, with regression tests.

### Known operational trap
- Rotating the app-role password leaves pgbouncer reporting `server login has been failing`
  until it is restarted/reloaded. Documented in `docs/SUPABASE.md`.

Runbook: `docs/SUPABASE.md`. Raw output: `docs/SUPABASE_VERIFICATION.md`.

## 2026-11-22 — Full product audit, dataset tooling, camera-metric fix

### Audit
- Added `docs/quality/` — 20 reports covering routes (23 pages, not 21), controls, API
  (82 operations / 69 paths), database integrity, security, AI validation, video pipeline,
  dataset acquisition/validation/licences, performance, accessibility, E2E, bug register and
  final acceptance. Each PASS carries the command or query behind it; blocked checks are labelled
  BLOCKED rather than passed.

### Fixed
- **B-002 (P2):** the command dashboard's "Cameras online" card counted `is_enabled`, so it read
  `13/13` while every camera was `offline`/`unknown`. It now counts `connection_status === "online"`
  and the hint says so. Verified by rebuild and by the SQL status distribution.
- **B-001 (P3):** dataset download instructions printed the archive stem as the `--dataset`
  argument; the dataset key is now passed explicitly.

### Dataset pipeline
- Added `datasets/manifest.yaml`, `datasets/README.md`, the full directory contract, and
  `scripts/datasets/` (`download`, `verify_downloads`, `extract`, `inspect`, `validate_annotations`,
  `prepare`, `evaluate_models`, `build_fixtures`).
- The pipeline is proven on a reproducible synthetic RDD fixture: size/SHA-256/zip check, safe
  extraction, 3 images / 2 VOC files / 1 corrupt image detected, VOC validation clean, deterministic
  sequence-aware split, and IoU evaluation producing `precision=0.6667 recall=1.0 f1=0.8`. Without a
  predictions file the evaluator exits BLOCKED instead of inventing numbers.
- **Real acquisition BLOCKED:** RDD2022 India S3 → HTTP 403; AI City Track 4 Drive → HTML
  interstitial with 0 bytes; BDD100K → login/licence required. Exact manual steps are in
  `docs/quality/DATASET_ACQUISITION_REPORT.md`; no placeholder data was substituted.

## 2026-11-22 — Endpoint audit, Supabase support, dataset intake

### Every endpoint is now exercised
- Added `tests/integration/test_endpoint_coverage.py`. It runs the full dependency chain
  (registry → camera → signed upload → job → incident → accident import → hotspots → investigation →
  recommendation → work order → completion evidence → independent verification → audit → WebSocket)
  and then diffs the calls it made against `app.openapi()`. A documented operation that is never
  called fails the test, so new routes cannot ship unexercised.
- Added a second test that replays every documented operation without a session and fails on any 2xx
  outside the five intentional pre-auth endpoints (health probes, the static permission catalog, the
  CSRF bootstrap cookie and idempotent logout).
- Generated `docs/ENDPOINT_AUDIT.md` (82 operations / 68 paths) from the live OpenAPI document.
- *Verified:* the suite passes; the assertions found the real contract differences that had been
  guessed wrong in older tests (change-password/logout return 204, unsupported media is 415 not 422,
  a work order must go `pending → assigned → in_progress`).

### Supabase support
- `apps/api/app/db/urls.py` normalises Supabase's plain `postgresql://` URIs to the psycopg driver,
  injects `sslmode`, and disables named prepared statements behind the transaction pooler (port 6543).
- Alembic escapes `%` in generated passwords before handing the URL to configparser.
- `scripts/supabase_setup.py` inspects a database (version, TLS, PostGIS schema, `pgcrypto`, RLS
  policies, app-role attributes), can create the extensions and the `roadguard_app` role with
  `NOSUPERUSER NOBYPASSRLS NOINHERIT`, set its `search_path` to include `extensions`, apply grants,
  re-revoke `UPDATE`/`DELETE` on `audit_logs`, write `.env` and run migrations. Passwords are never
  echoed.
- `docker-compose.yml` now reads `COMPOSE_DATABASE_MIGRATION_URL` / `COMPOSE_DATABASE_APP_URL`
  (local container defaults preserved), plus `DATABASE_SSL_MODE` and a connect timeout.
- Added `docs/SUPABASE.md` and the Supabase block in `.env.example`.
- *Verified:* URL/pooler unit tests pass; the inspector reports `[ok]` for every row against the
  bundled PostGIS container. **No Supabase project was available**, so a live switch is still owed.

### Dataset research and intake
- Added `docs/DATASETS.md`: the public corpora that actually exist (AI City Challenge 2020 Track 4,
  DoTA, the ACCIDENT benchmark, IDD/IDD-CRS, WTS, Nexar, CCD), their access terms, and the honest
  conclusion that no downloadable Indian municipal fixed-CCTV accident corpus exists.
- Added `scripts/prepare_dataset.py`: probes clips with OpenCV, SHA-256 hashes them, enforces the API's
  container/size/duration/resolution limits, writes a provenance manifest and can ingest ready clips
  through the normal upload → job flow (`--upload`).
- *Verified:* the synthetic demo clip validates and produces `datasets/manifests/prepared.json`.

### Test pack repair
- `tests/integration/test_database.py` required a `db_engine` fixture that did not exist; added it.
- `tests/unit/test_recommendations.py` used a fixture scoped to another class and asserted text the
  deterministic analyser never emits; moved the fixture and corrected the expectations.
- `tests/unit/test_responsibility.py` and `test_hotspots.py` used bare `Mock()` sessions that could not
  be iterated; replaced with ordered stubs that mirror the real queries.
- `tests/integration/test_video_pipeline.py` had a mangled module-level test and a stray assertion;
  rewritten against the real 415/413 contract, including proof that a rejected container creates no job.
- `tests/unit/test_event_detection.py` asked the pedestrian rule to fire on constant separation and the
  motion rules on too-short tracks; replaced with genuinely converging/decelerating scenarios.
- *Result:* `pytest` passes (all tests, no skips except the pre-existing one), `ruff` clean.

## 2026-11-18 — Containerized stack verified

- **Celery entrypoint was wrong.** `python -m ai_engine.workers.celery_app worker …` made Celery parse
  the module path as a subcommand. Compose and the worker Dockerfile now use
  `celery -A ai_engine.workers.celery_app:celery_app worker --pool=solo`.
- **`.env` silently disabled the container queue.** Compose interpolated
  `JOB_RUNNER=${JOB_RUNNER:-celery}` from the development `.env` (`polling`), so the API never
  enqueued and the Celery worker sat idle. The compose stack now pins `JOB_RUNNER: celery`;
  bare-metal runs can still use `polling` with `polling_worker.py`.
- **Presigned URLs pointed at an unreachable host.** Inside compose the bucket is `minio:9000`, which a
  browser cannot resolve. Added `S3_PUBLIC_ENDPOINT_URL`: object operations use the internal endpoint,
  URL signing uses the browser-reachable one.
- **The smoke script mishandled absolute signed URLs.** With S3 the upload and evidence URLs are
  absolute; the script concatenated them onto the API base (`http://…:8000http://…`). Added an
  `absolute_url()` helper that works for both the local and S3 backends.
- **Web image baked the wrong API address.** `next.config` rewrites and `NEXT_PUBLIC_*` values are
  resolved at build time, so the standalone build called `127.0.0.1:8000` inside its own container and
  every proxied request returned 500. The web Dockerfile now takes build args (`API_INTERNAL_URL`,
  `NEXT_PUBLIC_WS_URL`, tile URL/attribution) wired from compose.

*Verified after the fixes:* all seven services up (`postgres`, `redis`, `minio`, `minio-init`, `api`,
`worker`, `web`); `docker compose build api worker web` succeeds; `scripts/demo_smoke.py
--external-worker` completes **12/12 against the containers** with
`job_succeeded events=1 detections=177` in the Celery worker and evidence fetched through a MinIO
presigned URL; the browser loads the production web container, proxies anonymous calls as `401`,
signs in, and `/command` renders live metrics with realtime status "Connected (ticket-authenticated)".

## 2026-11-18 — Release candidate for the local demo environment

### Frontend (new)
- Next.js 16 App Router application (`apps/web`) with Tailwind CSS 4: **24 routes**.
  - Dark Command Center: overview, cameras, monitoring, videos & jobs, events, event detail,
    hotspots, investigations, investigation detail.
  - Light Administrative Portal: overview, departments, contractors, assets, contracts, case
    register + detail, work orders + detail, analytics, audit trail, users & roles.
- Shared UI primitives (cards, tables, badges, metrics, form fields, empty/loading/error/permission
  states), a DEMO banner on every shell, and a table alternative beside every map.
- Typed API client with refresh-on-401, CSRF header from the double-submit cookie and a single retry;
  session context exposes permissions so controls are gated *in addition to* server checks.
- Realtime client: 60-second ticket, reconnect with backoff, visible connection state, events treated
  as refresh hints only.
- *Verified:* `npx tsc --noEmit` clean, `npx next build` success, browser sign-in → `/command` with
  live metrics, map and event list.

### Backend fixes found by demos and tests
- **Evidence download returned 500.** `FileResponse` received a file object; replaced with a chunked
  `StreamingResponse` that closes the handle. Signed URLs now carry `content_type`/`filename` for the
  local backend.
- **Work-order demo skipped a state.** The demo attempted `pending → in_progress`; the state machine
  correctly rejects it. The smoke test now acknowledges (`assigned`) first, proving the transition map
  instead of bypassing it.
- **A separation-of-duties assertion was wrong, not the rule.** The original check used a reviewer who
  had not completed the work. It now proves the *completing* engineer cannot verify.
- **WebSocket events never reached in-process subscribers.** `publish_event` only published to Redis;
  it now also publishes to the in-process hub, hopping onto each subscriber's loop with
  `call_soon_threadsafe` because request handlers run in worker threads.
  *Verified:* a live socket received `incident.reviewed` after a review request.
- **Realtime unsubscribe** matches by queue identity instead of rebuilding a set mid-iteration.

### Tests (new, executed)
- `tests/unit` — tracker (IoU, class-consistent matching, retained short tracks, image-plane speed
  proxy), event rules (near-miss fires on convergence, silent on parallel traffic, collision needs
  sustained overlap, uncalibrated rules report `unavailable`, event types are `_candidate` only),
  permissions (auditor read-only, engineer cannot verify, platform-only permission), work-order
  transitions (no illegal jumps, terminal states), media validation (traversal-safe names,
  size/MIME/extension, container signature), rate limiter.
- `tests/integration` — anonymous 401s, wrong-password/unknown-email rejection, CSRF rejection,
  session identity, cross-tenant camera/incident/evidence access returning **404**, disjoint tenant
  record sets, auditor write denials, realtime ticket shape/expiry, and **audit immutability executed
  directly against PostgreSQL with the application role** (UPDATE and DELETE both rejected; rows
  unchanged).
- *Result:* `61 passed`. Ruff clean across `apps/api`, `ai-engine`, `scripts`, `tests`.

### Infrastructure
- Pinned all Python dependencies from the verified environment (API, engine, dev).
- Added `infrastructure/docker/{api,worker,web}.Dockerfile`, `.dockerignore`, `pyproject.toml`
  (pytest + ruff), and `shared/schemas/realtime_event.schema.json`.
- **MinIO image source changed.** `minio/minio` and `minio/mc` were removed from Docker Hub
  (September 2026) and quay.io now rejects anonymous pulls, so compose uses
  `cgr.dev/chainguard/minio` (same server, same S3 API/format) with a TCP readiness check, and bucket
  creation moved to `amazon/aws-cli` (`create-bucket` + `head-bucket`; MinIO rejects the AWS
  `put-public-access-block` payload, and MinIO buckets are private without an anonymous policy).
  *Verified:* services healthy, bucket created, S3 backend put/stat/read/checksum/presigned GET+PUT/
  delete probe succeeded.

### Documentation
- Added `README.md`, `docs/IMPLEMENTATION_STATE.md`, `docs/KNOWN_LIMITATIONS.md`,
  `docs/DECISIONS_AND_GLOSSARY.md` and this changelog.
- Recorded the two missing specification documents (`12_DEMO_DATA_AND_SCENARIO.md`,
  `13_DECISIONS_AND_GLOSSARY.md`) as gaps instead of inventing them.

## 2026-11-17 — Core platform

- FastAPI application with 68 documented paths under `/api/v1`, one response envelope, request-id
  middleware, structured logging, typed errors, health/readiness.
- SQLAlchemy models with naming conventions, UUID keys and composite tenant foreign keys; Alembic
  migrations `a0f8b507499d` (schema) → `b1c2d3e4f5a6` (security layer) → `837c7ef69730` (coordinates).
- Argon2 passwords, JWT access cookie, rotating refresh sessions (hash stored server-side), CSRF
  double-submit, login rate limiting, logout and password change.
- Two database roles: migration owner and `roadguard_app` (NOSUPERUSER, NOBYPASSRLS); RLS on tenant
  tables; append-only audit (grants revoked, trigger enforcing owner-only writes);
  `SECURITY DEFINER claim_ai_job(...)` for the worker.
- AI engine: decoder + sampler, colour-marker synthetic-scene detector, YOLO adapter (import-guarded),
  IoU tracker (ByteTrack adapter), six versioned event rules with explicit `unavailable` states,
  annotated frame + event clip evidence, deterministic investigation analysis with optional LLM
  adapter, shared `process_job()` used by Celery and the polling worker.
- Scripts: synthetic clip generator, idempotent two-tenant seed with DEMO markers, 12-step HTTP
  workflow smoke test.
