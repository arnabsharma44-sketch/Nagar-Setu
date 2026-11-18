# ROADGUARD AI — Implementation Changelog

Newest first. Each entry records what changed, why, and how it was verified.

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
