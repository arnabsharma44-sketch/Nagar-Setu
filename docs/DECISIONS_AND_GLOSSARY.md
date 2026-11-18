# ROADGUARD AI — Decisions and Glossary

`DOCUMENTATIONS/13_DECISIONS_AND_GLOSSARY.md` is not present in the specification pack, so the
decisions actually taken during implementation and the vocabulary used in code and UI are recorded
here. Nothing in this file changes an existing specification; where a spec was ambiguous, the choice
is listed with its rationale.

---

## A. Decisions

### D-01 — Two database roles in one PostgreSQL instance
**Context:** tenant isolation must survive application bugs; the specification asks for RLS as
defence in depth.
**Decision:** `roadguard` owns the schema and runs migrations/seeding; `roadguard_app`
(`NOSUPERUSER`, `NOBYPASSRLS`) serves the API. RLS policies are `FORCE`d only where necessary but
apply to the app role because it is not a superuser.
**Consequence:** migrations must set `roadguard_app_role` for grant statements, and tests that need
cross-tenant reads use `claim_ai_job` (see D-05) or the owner session.

### D-02 — Tenant isolation is four layers deep
1. Organization context is derived from the authenticated principal, never from a request field.
2. Composite foreign keys `(child_id, organization_id) → parent(id, organization_id)` make
   cross-tenant references impossible at the schema level.
3. Each transaction sets `app.current_organization_id` locally, so a leaked connection cannot carry
   the previous tenant's context.
4. RLS policies filter every tenant table for the app role.
**Consequence:** cross-tenant reads by UUID return **404**, not 403, so record existence does not
leak (asserted in `tests/integration/test_api_security.py`).

### D-03 — API never processes media
Uploads go browser → private storage via a short-lived signed URL, then a job row is created. No
decoding, no inference and no clip extraction happens inside a request.
**Consequence:** a demo needs the worker running; job retry is idempotent through the job's
idempotency key.

### D-04 — Two job execution paths, one implementation
`ai_engine/pipeline.process_job()` is shared by the Celery task and by `polling_worker.py`
(claim/lease with `SELECT … FOR UPDATE SKIP LOCKED`). The polling worker exists so the prototype can
run without a broker; the Celery path is the deployment path.

### D-05 — One sanctioned cross-tenant read
The worker must find jobs across all organizations. `claim_ai_job(p_worker_id, p_lease_seconds,
p_max_attempts)` is `SECURITY DEFINER` and returns only the job id and its organization id; everything
after that runs inside `tenant_session(organization_id)`. No other cross-tenant path exists.

### D-06 — Detector default is honest, not impressive
`DETECTOR_BACKEND=synthetic_scene` performs real OpenCV segmentation on a locally generated clip and
persists `synthetic_scene_v1` plus a `SYNTHETIC_SCENE_DETECTOR` limitation on every artefact. The YOLO
adapter is import-guarded and fails loudly when its dependency is missing.
**Rationale:** shipping a fake "YOLO" label would violate the responsible-AI rules; an unverified
detector that says so is defensible.

### D-07 — Event rules declare their own limits
Each rule returns `status="evaluated"` or `status="unavailable"` with a note. Wrong-way and
signal-line crossing are unavailable without lane/stop-line calibration. Scores are heuristics in
`[0, 1]`; every candidate carries `CAMERA_NOT_METRIC_CALIBRATED`, `IMAGE_PLANE_MEASUREMENT_ONLY` and
`CANDIDATE_OBSERVATION_NOT_CONFIRMED_EVENT`.

### D-08 — Storage is an interface
`LocalStorageBackend` (signed API URLs) and `S3StorageBackend` (presigned URLs) implement the same
protocol. Evidence and footage keys are prefixed with the organization id, so a leaked URL reveals
nothing about other tenants, and downloads re-check tenant scope before signing.

### D-09 — Cookies, not bearer tokens in JavaScript
Access JWT (15 min) and rotating refresh token live in `HttpOnly` cookies; the refresh token's hash is
stored in `refresh_sessions` so it can be revoked. A double-submit CSRF header protects unsafe
methods (login, refresh and health are exempt). The browser never holds a token a script can read.

### D-10 — Next.js proxies the API
`/api/*` is rewritten to the FastAPI service so cookies stay first-party and CORS credentials are
unnecessary. The internal service URL is a server-side environment variable.

### D-11 — WebSocket is a hint channel
Messages carry `event_type` + ids only. Clients refetch REST after receiving one. Tickets are
single-use, 60-second JWTs; the organization comes from the ticket, never from the client. Publishing
goes to the in-process hub **and** Redis so a single-process demo receives events without a broker.

### D-12 — Recommendations need a second pair of eyes
A recommendation is created as `draft` by its author; approval requires `recommendation:approve` and
the server rejects self-approval. Work-order completion and verification are similarly separated:
`work_order:complete` and `work_order:verify` sit with different roles and the submitter cannot
verify their own completion.

### D-13 — Audit is append-only at the database level
`UPDATE`/`DELETE` on `audit_logs` are revoked from the app role and a trigger rejects non-owner
writes. Enforced by test, not only by convention.

### D-14 — MinIO image source
`minio/minio` and `minio/mc` disappeared from Docker Hub in September 2026 and quay.io refuses
anonymous pulls, so compose uses `cgr.dev/chainguard/minio` (same server and S3 API) and creates the
bucket with `amazon/aws-cli`. This is an infrastructure source change, not an architecture change:
storage remains private S3-compatible object storage.

### D-15 — Separate internal and public S3 endpoints
**Context:** inside Compose the bucket is `minio:9000`; a browser cannot resolve that name, so a
presigned URL signed against it is useless outside the Docker network.
**Decision:** object operations use `S3_ENDPOINT_URL`; URL signing uses `S3_PUBLIC_ENDPOINT_URL` when
set (it falls back to the internal endpoint). Compose sets the public value to `http://localhost:9000`.
**Consequence:** a deployment behind a proxy must point the public value at the externally reachable
bucket host, or terminate presigned traffic at the API instead.

### D-16 — Client-visible configuration is build-time
**Context:** `next.config` rewrites and `NEXT_PUBLIC_*` variables are resolved when the Next build
runs, not when the container starts.
**Decision:** the web image takes `API_INTERNAL_URL`, `NEXT_PUBLIC_WS_URL` and the map tile settings as
build args, supplied by Compose. Runtime-only `NEXT_PUBLIC_*` overrides are not supported.
**Consequence:** changing the API host or tile server requires rebuilding the web image, which is
recorded in the README and in the compose build args.

### D-17 — Demo footage is generated, never downloaded
`scripts/generate_demo_clip.py` renders a synthetic intersection clip with OpenCV. No third-party
footage is redistributed, and every artefact is traceable to a generator run.

---

## B. Glossary

| Term | Meaning in this codebase |
| --- | --- |
| **Candidate event** | An AI-produced observation awaiting human review (`review_status=pending`). Not an accident. |
| **Incident** | The stored record of an event, whether AI-produced or manually reported. `source_kind` distinguishes them. |
| **Confirmed observation** | An incident a human reviewer accepted. Still not a legal finding. |
| **Historical accident record** | An imported CSV row with its own `source_name`, `source_reference` and `verification_status`. Never merged into AI counts. |
| **Evidence artefact** | A private stored file (annotated frame, event clip, completion photo) with a checksum, type and timestamp. |
| **Hotspot / cluster** | A concentration of located records produced by DBSCAN within a radius. Not an exposure-adjusted risk rate and not a causation claim. |
| **Investigation / case** | A record holding observed facts, hypotheses, missing information, evidence references and human decisions as separate fields. |
| **Hypothesis** | A possible root cause with a confidence *label* and cited supporting records. Never a conclusion. |
| **Recommendation** | A proposed corrective action requiring independent approval before a work order exists. |
| **Work order** | The actionable instruction to a department, with a validated state machine and completion evidence. |
| **Verification** | A different user's decision that completion evidence satisfies the work order. |
| **Separation of duties** | The rule that the person who completed work cannot verify it (and that a recommendation's author cannot approve it). |
| **Simulated live** | A replay of recorded footage explicitly labelled SIMULATED LIVE; never a real camera feed. |
| **DEMO** | Synthetic seeded or generated data, labelled in the UI and stored with `is_demo=true`. |
| **Image-plane measurement** | A quantity in pixels or normalised pixels. Never metres, m/s or seconds-to-collision. |
| **Ticket (realtime)** | A single-use 60-second JWT that authorises one WebSocket connection for one organization. |
| **Claim / lease** | A worker's time-boxed ownership of a job row, with attempts and retry limits. |
