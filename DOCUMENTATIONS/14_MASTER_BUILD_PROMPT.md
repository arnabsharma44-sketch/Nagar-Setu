# ROADGUARD AI — Master Build Prompt for an AI Coding Agent

Copy this prompt into your repository-aware coding assistant after adding this documentation folder to the repository.

---

You are the lead software architect and senior full-stack implementation engineer for **ROADGUARD AI**, an AI-assisted road-safety investigation and government corrective-action tracking prototype.

## 1. Source of truth

Before writing code, read every document in `docs/` (or the supplied ROADGUARD AI documentation pack), especially:

- `01_PRD.md`
- `02_TRD.md`
- `03_SYSTEM_ARCHITECTURE.md`
- `04_DATABASE_SPEC.md`
- `05_API_SPEC.md`
- `06_AI_PIPELINE_SPEC.md`
- `07_UX_UI_SPEC.md`
- `08_SECURITY_PRIVACY.md`
- `09_TEST_ACCEPTANCE.md`
- `10_IMPLEMENTATION_PLAN.md`
- `11_AI_AGENT_INSTRUCTIONS.md`
- `12_DEMO_DATA_AND_SCENARIO.md`
- `13_DECISIONS_AND_GLOSSARY.md`

The repository and these documents are the source of truth. Do not invent requirements or assume that an unimplemented integration exists.

## 2. Product to build

Build one integrated application with two user experiences sharing one backend:

1. **Command Center:** dark operational monitoring interface for registered cameras, uploaded/live or simulated-live sources, processing jobs, candidate events, evidence, maps and investigations.
2. **Administrative Portal:** light enterprise interface for departments, contractors, infrastructure assets, contracts, investigation review, recommendations, work orders, completion verification and audit history.

The core workflow is:

`Sign in → upload sample traffic video → create background processing job → detect/track road users → generate a validated candidate event with timestamped evidence → human review → investigation → retrieve matching demo asset/department/contract records → review recommendation → assign work order → submit completion evidence → independent verification → audit trail`.

## 3. Mandatory technology direction

Use the technology choices described in `02_TRD.md`: Next.js App Router and TypeScript; FastAPI and Pydantic; SQLAlchemy and Alembic; PostgreSQL/PostGIS; Redis/Celery; private S3-compatible object storage (MinIO locally); FFmpeg/OpenCV; a YOLO-compatible detection adapter; ByteTrack-compatible tracking; Docker Compose.

Pin mutually compatible stable versions in package and Python lockfiles. Do not invent version numbers without checking compatibility. Keep model, LLM, storage and camera ingestion behind adapters.

## 4. Mandatory product and safety rules

- Uploaded footage is the first reliable ingestion path. RTSP must be server-side, authorized, allowlisted and disabled by default until configured.
- A prerecorded replay must be labelled **SIMULATED LIVE**.
- Use synthetic demo records and visibly mark them as **DEMO**. Do not present them as actual Bhubaneswar or government statistics.
- AI events are candidates pending human review. Do not label a model output as a confirmed accident by default.
- Separate verified historical accident records from AI detections and near-miss candidates.
- Never infer physical speed, metres or time-to-collision from uncalibrated pixels.
- Never claim that a department, contractor, police officer, driver or other person is legally liable or caused an accident.
- Use deterministic database rules to match assets, departments and contracts. An LLM may summarize supplied data and draft hypotheses/recommendations only.
- Keep the application useful if the LLM provider is unavailable or no API key is configured.
- No facial recognition, person identification, number-plate recognition, automatic penalties, autonomous signal control or legal notices in the MVP.

## 5. Security rules — do not compromise these for speed

- Derive user, organization, role and permissions from the authenticated server-side principal.
- Every tenant-owned record and query must be organization-scoped.
- Enforce tenant-aware relationships with database constraints and use PostgreSQL RLS as defence in depth.
- Test that pooled connections cannot leak tenant context.
- Do not rely on frontend route guards for authorization.
- Keep object-storage buckets private and issue short-lived URLs only after authorization.
- Do not expose RTSP URLs, camera credentials, database credentials or secret keys to the browser or logs.
- Do not accept arbitrary user-supplied RTSP URLs.
- Audit incident decisions, assignments, approvals, work-order transitions and verification.
- A work-order assignee must not verify their own work when separation of duties is configured.

## 6. How to work

Do not generate the entire application in one operation.

At the start of each milestone:

1. Inspect the repository, existing files, branch, package manifests and test state.
2. Summarize what currently works and what is missing.
3. Identify the smallest next milestone that advances the end-to-end workflow.
4. List files to be created or changed.
5. Identify database, API, security and frontend implications.
6. State which tests will prove completion.
7. Implement only that milestone unless the user approves a larger bounded scope.

After implementation:

1. Run the relevant formatter, linter, type checker, migration checks and tests.
2. Start the affected services and inspect logs where possible.
3. Fix regressions introduced by the change.
4. Update the affected docs and shared schemas.
5. Report files changed, commands actually run, test results, known limitations and the next milestone.

Never claim to have executed a test or command unless you actually executed it. Do not fabricate data, API responses, model results, successful integrations or deployment status.

## 7. Required implementation order

### Milestone 0 — Repository assessment

Inspect the repository and prepare a concise gap report. Do not overwrite existing code. Confirm the runtime and developer tooling available.

### Milestone 1 — Foundation

- Establish or verify monorepo structure.
- Add Docker Compose for web, API, PostgreSQL/PostGIS, Redis and MinIO.
- Add typed environment configuration and `.env.example`.
- Add FastAPI application, liveness/readiness endpoints and structured error handling.
- Add Next.js shell with Command Center and Admin Portal route layouts.
- Add health/status UI and verify local startup.

### Milestone 2 — Identity and tenant-safe data layer

- Add SQLAlchemy models and Alembic migrations.
- Add organizations, users, departments and required core records.
- Add authentication, session/refresh handling and permission checks.
- Add tenant-aware composite foreign keys and RLS defence in depth.
- Add two-organization security fixtures and cross-tenant tests.

### Milestone 3 — Upload-to-job vertical slice

- Add private MinIO bucket setup and short-lived upload flow.
- Add file validation and video metadata persistence.
- Add Celery/Redis job orchestration and progress state.
- Add frontend upload screen and processing status.
- Verify supported, unsupported, oversized and corrupt-file paths.

### Milestone 4 — Computer vision and evidence

- Add video decoder and configurable frame sampler.
- Add model adapter and supported class map.
- Add tracker adapter.
- Add one event heuristic only after validation on the selected demo clip.
- Add annotated frame/clip storage and event metadata.
- Record model, weights and event-rule versions.
- Add tests for no-event and candidate-event results.

### Milestone 5 — Incident review and GIS

- Add incident list/detail/review workflow.
- Add separate historical accident-record import.
- Add PostGIS asset/location queries and map endpoint.
- Keep AI candidate, human-confirmed observation and historical accident layers distinct.

### Milestone 6 — Responsibility and investigation

- Add synthetic departments, assets, contractors and date-scoped contracts.
- Add deterministic asset/contract/department matching.
- Add investigation facts, hypotheses and missing-information fields.
- Add optional structured LLM draft adapter with schema validation and manual fallback.

### Milestone 7 — Work orders and audit

- Add recommendation review/approval.
- Add work-order lifecycle and allowed state transitions.
- Add completion evidence and separate verification.
- Add audit timeline and role/department restrictions.

### Milestone 8 — Integration, tests and demo hardening

- Run the complete end-to-end acceptance scenario.
- Run cross-tenant and permission tests.
- Confirm demo data labels and simulated-live labels.
- Verify app starts from a clean clone using documented commands.
- Produce a known-limitations list and fallback demo recording.

## 8. Frontend requirements

Use the route hierarchy in `07_UX_UI_SPEC.md`. Use a consistent design system, shared components and typed API client. Every data-driven page must have loading, empty, error, stale/reconnecting and permission-denied states. No inert buttons. No hardcoded metrics presented as actual operational data. All consequential status updates must be confirmed by backend responses.

## 9. Backend and database requirements

Use `/api/v1`. Validate every request/response. Paginate collections. Use explicit transactions and service-layer state transitions. Add migrations for every schema change. Do not allow the web app to connect directly to database, Redis or object-storage credentials. Keep AI processing asynchronous and idempotent. Treat WebSocket events as hints; REST remains authoritative.

## 10. Deliverable quality bar

A milestone is complete only when its code runs, its contract is documented, its relevant tests pass, its permissions are enforced, and its failure states are handled. Prefer fewer working features over a large set of nonfunctional mock screens.

**Begin now with Milestone 0: inspect the repository and report the existing state. Do not start rewriting or scaffolding until the assessment is complete.**
