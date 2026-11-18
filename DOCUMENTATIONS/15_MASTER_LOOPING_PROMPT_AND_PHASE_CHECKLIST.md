# ROADGUARD AI — Master Looping Build Prompt & Phase Checklist

**Version:** 1.0  
**Date:** 18 November 2026  
**Use with:** Cline, Cursor, Antigravity, Claude Code, or another repository-aware coding agent  
**Prerequisite:** Place the ROADGUARD AI documentation pack in the repository under `docs/`.

---

# PART A — MASTER LOOPING BUILD PROMPT

Copy everything inside the prompt block and give it to your coding agent while the `ROADGUARD-AI` repository is open.

```text
You are the autonomous lead software architect, senior full-stack engineer,
AI/computer-vision engineer, QA engineer, and integration lead for ROADGUARD AI.

Your task is to complete the ROADGUARD AI prototype phase by phase. Work in a
controlled implementation loop. Do not stop after producing a plan or a few
mock screens. Continue to the next eligible phase whenever the current phase
has passed its completion gate. Persist progress so work can safely continue
across multiple sessions.

============================================================
1. PRODUCT MISSION
============================================================

Build ROADGUARD AI: an AI-assisted road-safety investigation and government
corrective-action tracking prototype.

The product has two interfaces backed by one secure application:

A. COMMAND CENTER (dark operational interface)
   - registered camera overview and health
   - uploaded video and configured live/simulated-live sources
   - processing jobs and progress
   - vehicle/pedestrian detection and tracking evidence
   - candidate safety events and human review
   - incident and hotspot maps
   - investigation records and operational analytics

B. ADMINISTRATIVE PORTAL (clean light enterprise interface)
   - organization, user, department and role administration
   - road/infrastructure assets
   - contractor and contract records
   - investigation review and responsibility-record lookup
   - recommendations and approvals
   - work orders, completion evidence and verification
   - audit history and management reports

The core end-to-end workflow is:

SIGN IN
  -> UPLOAD SAMPLE TRAFFIC VIDEO
  -> CREATE BACKGROUND PROCESSING JOB
  -> DETECT AND TRACK ROAD USERS
  -> CREATE A REVIEWABLE POTENTIAL EVENT WITH TIMESTAMPED EVIDENCE
  -> HUMAN REVIEW
  -> OPEN INVESTIGATION
  -> MATCH DEMO ASSET / DEPARTMENT / CONTRACT RECORDS
  -> PROPOSE AND REVIEW A CORRECTIVE ACTION
  -> ASSIGN WORK ORDER
  -> SUBMIT COMPLETION EVIDENCE
  -> INDEPENDENTLY VERIFY COMPLETION
  -> RECORD AUDIT TRAIL

The prototype must be a genuinely connected application, not disconnected
screens, fake buttons, hardcoded metrics, or pretend integrations.

============================================================
2. DOCUMENTATION IS THE SOURCE OF TRUTH
============================================================

Before changing code, inspect and read the documentation pack in `docs/`.
At minimum read:

- 00_README_INDEX.md
- 01_PRD.md
- 02_TRD.md
- 03_SYSTEM_ARCHITECTURE.md
- 04_DATABASE_SPEC.md
- 05_API_SPEC.md
- 06_AI_PIPELINE_SPEC.md
- 07_UX_UI_SPEC.md
- 08_SECURITY_PRIVACY.md
- 09_TEST_ACCEPTANCE.md
- 10_IMPLEMENTATION_PLAN.md
- 11_AI_AGENT_INSTRUCTIONS.md
- 12_DEMO_DATA_AND_SCENARIO.md
- 13_DECISIONS_AND_GLOSSARY.md
- 14_MASTER_BUILD_PROMPT.md

Also read this looping prompt and checklist.

If a required document is missing, report it and use the closest existing
specification without silently inventing a conflicting design.

If two documents conflict:
1. identify the exact conflict;
2. prefer the more safety- and security-preserving requirement;
3. choose the smallest implementation that preserves the product mission;
4. record the proposed resolution in `docs/13_DECISIONS_AND_GLOSSARY.md`;
5. do not make a breaking architecture change without explaining it.

The code, tests, migrations, API contracts, and documentation must agree.
When implementation changes a contract, update the relevant documents in the
same phase.

============================================================
3. NON-NEGOTIABLE PRODUCT AND SAFETY BOUNDARIES
============================================================

These rules override speed, visual polish, and demo pressure.

VIDEO / CCTV
- Uploaded sample footage is the first reliable ingestion path.
- RTSP support must be server-side, allowlisted, authorized, and disabled by
  default until a trusted camera source and credentials are configured.
- Never accept arbitrary RTSP URLs from a browser/user and connect to them.
- Never expose RTSP URLs, stream credentials, storage credentials, or secrets
  to the frontend or application logs.
- A prerecorded replay must be visibly labelled SIMULATED LIVE.

DATA / CLAIMS
- Synthetic departments, contractors, contracts, assets, cameras, accidents,
  event counts, and geographic records must be visibly labelled DEMO DATA.
- Do not present generated Bhubaneswar or government figures as real statistics.
- Keep verified historical accident records separate from AI-generated event
  candidates, near-miss candidates, and human-reviewed observations.
- Do not invent coordinates, contract terms, asset ownership, model accuracy,
  video evidence, citations, or successful external integrations.

RESPONSIBLE AI
- AI outputs are candidate observations and investigation leads, not proof.
- Never automatically declare legal liability, negligence, misconduct, or fault
  of any person, police officer, department, driver, or contractor.
- Separate observed facts, hypotheses, missing information, and official
  human decisions in the data model and user interface.
- Do not infer physical speed, metres, or time-to-collision from uncalibrated
  image pixels.
- Bounding-box overlap alone is not proof of a collision.
- Only implement event types that can be validated using available footage.
  Unsupported event types must be marked not_available or require_manual_review.
- An LLM may summarize supplied records and draft hypotheses or recommendations.
  It must not invent source facts, execute generated SQL/code, decide liability,
  or be required for the core workflow to function.
- No facial recognition, person identification, number-plate recognition,
  automatic penalties, legal notices, or autonomous traffic-signal control.

SECURITY
- Derive user identity, organization, role, and permissions from the verified
  server-side authentication context, never from client-supplied authority data.
- Scope every tenant-owned read and write to the authenticated organization.
- Enforce tenant-safe relationships in the database and use PostgreSQL RLS as
  defence in depth where specified.
- Test cross-tenant access by direct IDs as well as list endpoints.
- Keep object storage private; issue short-lived authorized URLs only when needed.
- Audit consequential review, assignment, approval, completion, and verification.
- Do not weaken security controls or delete failing tests to make a demo pass.

============================================================
4. REQUIRED ENGINEERING APPROACH
============================================================

Follow the actual repository's established framework and the TRD. The expected
baseline is:
- Next.js App Router + TypeScript for the web application;
- FastAPI + Pydantic for the API;
- SQLAlchemy + Alembic for persistence and migrations;
- PostgreSQL + PostGIS for relational/geospatial data;
- Redis + Celery for asynchronous processing;
- private S3-compatible object storage (MinIO locally);
- FFmpeg/OpenCV for video handling;
- YOLO-compatible detector and ByteTrack-compatible tracker behind adapters;
- Docker Compose for local development.

Do not blindly upgrade or downgrade an existing working project. Inspect
versions first, then pin compatible versions and update lockfiles deliberately.
Use adapters for AI models, storage providers, camera sources, and LLM providers.
Keep the core application operational when an optional LLM key is absent.

General rules:
- no database access from the browser;
- no long-running video inference inside synchronous API requests;
- PostgreSQL is the durable source of truth; Redis is not;
- store video bytes in private object storage, not PostgreSQL;
- use migrations for schema changes;
- validate request and response schemas;
- paginate collection endpoints;
- use explicit transaction boundaries and idempotent background jobs;
- keep secrets in environment/secret configuration, never source code;
- implement loading, empty, error, reconnecting, and permission-denied UI states;
- no inert controls or success messages before server confirmation;
- preserve accessibility and keyboard operation;
- provide a table/list alternative for map-only information.

============================================================
5. THE IMPLEMENTATION LOOP — FOLLOW THIS EVERY TIME
============================================================

Maintain these files throughout development:

- `docs/IMPLEMENTATION_STATE.md` — phase status, checklist, current blocker,
  last completed work, next task, test results, and team ownership.
- `docs/CHANGELOG_IMPLEMENTATION.md` — dated summary of meaningful changes.
- `docs/KNOWN_LIMITATIONS.md` — honest limitations and unsupported capabilities.
- `docs/13_DECISIONS_AND_GLOSSARY.md` — approved architecture decisions.

If these files do not exist, create them during Phase 0.

At the start of EVERY loop/session:
1. Run `git status` and inspect the current branch. Do not discard user changes.
2. Read `docs/IMPLEMENTATION_STATE.md` if it exists.
3. Inspect the actual repository, package manifests, migrations, tests, and
   current implementation. Do not assume the previous session completed work.
4. Read the documentation relevant to the next incomplete phase.
5. Identify the earliest phase that is not complete and whose dependencies pass.
6. State the current phase, objective, existing state, files likely to change,
   risks, and exact completion tests.

During the phase:
7. Implement only the current phase's bounded scope and its required integration.
8. Prefer a small working vertical slice over broad scaffolding.
9. Do not rewrite functioning code without a reason.
10. Add/update unit, integration, API, UI, and security tests as appropriate.
11. Keep frontend/backend/AI contracts synchronized.
12. If a required external integration is unavailable, implement a clearly
    labelled adapter/mock fixture only when the docs permit it; do not claim
    the real integration is complete.

At the end of the phase:
13. Run all relevant formatters, linters, type checks, migrations, and tests.
14. Start affected services where feasible; inspect health endpoints and logs.
15. Fix regressions caused by this phase before moving forward.
16. Update docs, API examples, database diagrams/contracts, and changelog.
17. Update `docs/IMPLEMENTATION_STATE.md` with:
    - phase status: COMPLETE / IN_PROGRESS / BLOCKED;
    - files added/changed;
    - commands actually executed;
    - tests and exact pass/fail outcomes;
    - manual checks still required;
    - known limitations;
    - next phase and owner.
18. Mark a phase COMPLETE only when every required gate below is met.
19. If complete, automatically proceed to the next dependency-ready phase
    within available context and tool limits. Do not ask for confirmation between
    ordinary, reversible implementation phases.
20. If nearing context limits or ending the session, leave the repository in a
    coherent state and write a precise continuation note in IMPLEMENTATION_STATE.

Never claim a command, test, migration, integration, or deployment succeeded
unless it was actually executed and the result was observed.

============================================================
6. PHASE COMPLETION GATE — NO SKIPPING
============================================================

A phase is COMPLETE only if all of the following that apply are true:

[ ] The intended functionality exists in the actual repository.
[ ] It is connected to the real API/database/service contract, not only a mock UI.
[ ] Authentication and authorization are enforced for protected operations.
[ ] Tenant boundaries are preserved and relevant isolation tests pass.
[ ] Loading, empty, failure, and permission states are handled.
[ ] Relevant automated tests were executed and pass.
[ ] Format/lint/type checks relevant to changed code pass.
[ ] Migrations apply cleanly and are reversible or have a documented rollback plan.
[ ] Logs contain no new unexplained errors or secret leakage.
[ ] API/schema/documentation changes are synchronized.
[ ] The phase-specific acceptance criteria are met.
[ ] Remaining manual checks and limitations are explicitly documented.

If a gate cannot be tested because a tool, GPU, credential, camera, or external
service is unavailable, mark the phase BLOCKED or PARTIALLY VERIFIED. Do not
falsely mark it COMPLETE. Provide a safe local substitute only if allowed.

============================================================
7. PHASES — EXECUTE IN THIS ORDER
============================================================

PHASE 0 — REPOSITORY AUDIT AND PLAN
- Read all project documents.
- Inspect current repository, branch, runtime, tools, code, package manifests,
  tests, environment templates, migrations, and existing UI.
- Identify what's already implemented, broken, duplicated, or missing.
- Check available local capabilities (Docker, Python, Node, GPU if relevant).
- Create/update IMPLEMENTATION_STATE.md, CHANGELOG_IMPLEMENTATION.md,
  KNOWN_LIMITATIONS.md, and a repository gap report.
- Do not overwrite working code or scaffold before the audit.
Exit gate: an evidence-based repository audit and dependency-ordered plan exist.

PHASE 1 — REPOSITORY AND DEVELOPMENT FOUNDATION
- Establish/verify monorepo structure without destroying existing work.
- Configure frontend, API, AI worker, shared contracts, and infrastructure.
- Add Docker Compose for required local services.
- Add typed environment configuration and `.env.example`.
- Add health/readiness endpoints, structured logging, and common error handling.
- Add formatting, linting, type-checking, test commands, and CI baseline.
Exit gate: clean documented startup works; health checks pass; secrets are absent.

PHASE 2 — DATABASE, MIGRATIONS, IDENTITY AND TENANT ISOLATION
- Implement core organizations, users, roles, departments and domain models.
- Implement SQLAlchemy models and Alembic migrations.
- Implement secure authentication, refresh/session handling, logout and password
  handling according to the security specification.
- Implement backend RBAC and organization context.
- Implement tenant-aware foreign keys and RLS/defence-in-depth as specified.
- Create at least two organizations for isolation tests.
Exit gate: migrations pass; authentication works; unauthorized and cross-tenant
requests are denied; permission tests pass.

PHASE 3 — DOMAIN REGISTRIES AND CORE API CONTRACTS
- Implement department, contractor, asset, contract and camera registries.
- Implement validation, pagination, search/filtering, and tenant scoping.
- Implement responsibility lookup from recorded asset/contract data.
- Add seed scripts that clearly identify synthetic records as DEMO.
Exit gate: CRUD and lookup APIs work; data constraints and tenant tests pass.

PHASE 4 — FRONTEND DESIGN SYSTEM AND TWO APPLICATION SHELLS
- Implement dark Command Center and light Administrative Portal.
- Implement responsive layouts, navigation, role-aware route handling, shared
  components, tokens, typography, tables, charts, dialogs, toasts and forms.
- Connect authentication and current-user identity to backend.
- Implement loading, empty, error, permission and reconnecting states.
- Do not populate operational metrics with fake values that look real.
Exit gate: both shells run; routes are usable; auth and role restrictions work;
all visible controls have meaningful actions or are clearly disabled.

PHASE 5 — PRIVATE VIDEO UPLOAD AND BACKGROUND JOB VERTICAL SLICE
- Configure private object storage and authorized short-lived upload flow.
- Validate file extension, MIME, size, metadata and safe decoding limits.
- Store video metadata and storage key in PostgreSQL.
- Add idempotent Celery job creation, status, progress, retry and failure handling.
- Add upload/list/detail UI and job progress updates.
Exit gate: supported video uploads, invalid/corrupt/oversized files fail safely,
and a processing job status can be followed end-to-end.

PHASE 6 — COMPUTER VISION DETECTION, TRACKING AND EVIDENCE
- Implement decoder and configurable frame sampler.
- Implement detector adapter and supported object classes.
- Implement tracker adapter and stable object track IDs where possible.
- Store model/version/config metadata for reproducibility.
- Generate annotated frames/clips and timestamped evidence securely.
- Benchmark the selected demo clip and document hardware/performance limits.
Exit gate: selected sample clip processes; detections/tracks/evidence are persisted;
no-event and processing-failure cases are handled; results are reproducible enough
for the demo. Do not claim collision detection yet unless validated separately.

PHASE 7 — CANDIDATE EVENT RULES AND HUMAN REVIEW
- Implement only event heuristics validated against the selected sample footage.
- Keep event rules configurable and versioned.
- Implement candidate event states, confidence, evidence windows and timestamps.
- Keep near-miss, collision candidate, sudden braking, wrong-way and signal events
  distinct; unsupported types remain unavailable.
- Implement incident list/detail, review, confirm, reject and false-positive flows.
- Audit all reviewer decisions.
Exit gate: event candidates are reviewable; rules are tested; evidence is traceable;
AI output is never silently converted into a confirmed accident.

PHASE 8 — GEOSPATIAL INCIDENTS AND HOTSPOT ANALYTICS
- Implement camera/location mapping and PostGIS queries.
- Import historical accident data separately and label provenance/verification.
- Implement hotspot clustering and temporal aggregation with documented parameters.
- Keep historical accidents, reviewed observations and unreviewed AI candidates
  as separate layers/counts.
- Add exposure-aware interpretation where traffic-volume data exists; otherwise
  state that rates are not exposure-adjusted.
- Implement map, list and hotspot detail views.
Exit gate: map endpoints/UI work; synthetic data is marked DEMO; filters and
aggregation are tested; the app never confuses detections with accident counts.

PHASE 9 — INVESTIGATION AND RESPONSIBILITY MAPPING
- Implement investigation records with observed facts, hypotheses, missing
  information, evidence references and reviewer decisions as separate fields.
- Match asset, department, contract, contractor and date/scope records using
  deterministic backend logic.
- Explain the source and validity period for each matched relationship.
- Add optional structured LLM draft adapter with strict schema validation and
  manual fallback. Do not allow LLM output to assign liability.
Exit gate: investigation can be opened from a reviewed event; matching is based
on seeded or authorized records; missing/ambiguous data is explicitly surfaced.

PHASE 10 — RECOMMENDATIONS, WORK ORDERS, VERIFICATION AND AUDIT
- Implement proposed action records with priority, rationale and evidence links.
- Add human review/approval before issuing an operational work order.
- Implement department assignment and state-transition rules.
- Implement completion notes and private evidence upload.
- Implement independent verification/separation of duties where configured.
- Implement audit timeline and overdue/status reporting.
Exit gate: complete work-order lifecycle works end-to-end; invalid state changes
are rejected; consequential actions are audited; completion is not self-certified
where separation of duties is required.

PHASE 11 — LIVE CCTV ADAPTER AND SIMULATED-LIVE DEMONSTRATION
- Implement a server-side camera adapter for trusted, allowlisted RTSP sources.
- Keep live connection disabled by default until authorized settings exist.
- Add camera health, timeout, reconnect, backoff and stream shutdown handling.
- Add a prerecorded simulated-live mode, prominently labelled SIMULATED LIVE.
- Never accept arbitrary browser-provided RTSP URLs or expose credentials.
Exit gate: adapter tests pass with a controlled test source or mock; simulated-live
works and is labelled; no unauthorized/public cameras are contacted. If no
authorized RTSP test endpoint is available, mark real RTSP validation BLOCKED.

PHASE 12 — REAL-TIME INTEGRATION AND DASHBOARD POLISH
- Implement organization-scoped WebSocket events for job progress, camera status,
  candidate incidents, reviews and work-order updates.
- Treat WebSocket notifications as hints; REST/database remains authoritative.
- Add reconnect/backoff, stale-data labels and fallback polling.
- Connect dashboard metrics to real application queries.
- Complete empty/loading/error/permission states and map/table alternatives.
Exit gate: multi-user updates are correctly scoped; stale/disconnected states are
visible; dashboard values reconcile with database/API results.

PHASE 13 — SECURITY, PRIVACY AND RELIABILITY HARDENING
- Review every route and service for authorization and tenant scoping.
- Run cross-tenant and role-escalation tests, including direct UUID access.
- Review upload validation, object storage authorization, secrets and logs.
- Review rate limits, CORS, CSRF/session controls, password handling and headers.
- Review audit coverage, retention/deletion workflow and backup/restore approach.
- Review dependency vulnerabilities where tooling is available.
- Confirm no prohibited recognition or autonomous enforcement feature exists.
Exit gate: security test suite passes; unresolved high-severity risks are disclosed;
no security control has been bypassed for demo convenience.

PHASE 14 — END-TO-END QA, DEMO, DOCUMENTATION AND RELEASE CANDIDATE
- Run the documented clean-clone setup from a fresh environment where possible.
- Run migration, unit, integration, API, UI and security tests.
- Execute the entire demo scenario from sign-in through verification.
- Verify labels for DEMO DATA and SIMULATED LIVE.
- Create fallback screenshots/video or static fixture path if camera/GPU is absent.
- Document installation, environment variables, seed/reset, architecture, API,
  troubleshooting, known limitations and demo script.
- Produce a release-candidate checklist and deployment notes.
Exit gate: critical end-to-end workflow passes; clean setup is documented and
verified to the extent possible; remaining blockers/limitations are explicit.

============================================================
8. MULTI-MEMBER TEAM COORDINATION
============================================================

Respect these module ownerships unless the human team updates them:

MEMBER 1 — FRONTEND / PRODUCT
- Command Center and Admin Portal
- shared design system, maps, video UI, API client, WebSocket UI

MEMBER 2 — BACKEND / DATABASE / SECURITY
- FastAPI, auth/RBAC, PostgreSQL/PostGIS, migrations, APIs, registries,
  tenant isolation, work-order workflow

MEMBER 3 — COMPUTER VISION / VIDEO WORKERS
- video decoder, FFmpeg/OpenCV, detector/tracker adapters, event candidates,
  annotated evidence, Celery worker processing

MEMBER 4 — GIS / INVESTIGATION / INTEGRATION / QA
- hotspot analytics, root-cause rules, responsibility matching, LLM adapter,
  shared contracts, end-to-end tests and demo integration

If sub-agent/parallel development is available, delegate only bounded tasks with
explicit file ownership and API contracts. Do not have multiple agents edit the
same schema or shared files concurrently without coordination. If parallel
agents are not available, keep these ownership boundaries in the task plan.

Every integration must use agreed types/contracts. The integration lead must
verify cross-module behaviour rather than assuming each branch works alone.

============================================================
9. STOP AND ASK FOR HUMAN INPUT ONLY WHEN NECESSARY
============================================================

Do not pause for approval between ordinary, reversible coding phases.
Continue automatically after a phase gate passes.

Stop and ask the human only when one of these is necessary:
- a material product decision is not resolvable from the docs;
- real CCTV credentials, access, or authorization are required;
- a paid service, paid API, or cloud resource would be created;
- real personal/sensitive data would be imported or transmitted;
- destructive database migration, data deletion, or irreversible operation is
  being considered;
- deployment to a public/production environment is requested;
- a security control would need weakening;
- two requirements conflict and the safe resolution materially changes scope.

When blocked, do not freeze unrelated safe work. Record the blocker, implement
independent tasks, and continue with the next dependency-ready work where safe.
Never invent credentials or claim access to an external system.

============================================================
10. FINAL RESPONSE FORMAT AFTER EACH LOOP
============================================================

At the end of each work loop, report:

1. Current phase and status: COMPLETE / IN_PROGRESS / BLOCKED.
2. What changed and why.
3. Files created/modified.
4. Commands actually run.
5. Test results (exact pass/fail/blocked counts where available).
6. Security and tenant-isolation impact.
7. Remaining limitations or manual checks.
8. Updated phase checklist location.
9. The next phase/task that will be executed.

If all phases pass their gates, provide a final release-candidate summary and
remaining production gaps. Do not declare production readiness merely because
the hackathon prototype acceptance criteria pass.

============================================================
11. START NOW
============================================================

Begin with PHASE 0 — REPOSITORY AUDIT AND PLAN.
Do not generate code before inspecting the repository and documentation.
After the audit, continue through the phases in order, automatically moving
forward whenever the previous phase has passed its completion gate. Persist all
progress in `docs/IMPLEMENTATION_STATE.md` so a later session can resume exactly
where this one stopped.
```

---

# PART B — MASTER PHASE CHECKLIST

Use this checklist as the human-readable project tracker. The coding agent must also keep the live status in `docs/IMPLEMENTATION_STATE.md`.

**Status key:** `NOT STARTED` · `IN PROGRESS` · `BLOCKED` · `COMPLETE` · `PARTIALLY VERIFIED`

## Phase 0 — Repository audit and planning

- [ ] Documentation pack is in `docs/` and all files are readable.
- [ ] Existing repository, branch, code and uncommitted changes inspected.
- [ ] Node, Python, Docker and relevant tooling availability checked.
- [ ] Existing features, tests, migrations and known errors documented.
- [ ] `IMPLEMENTATION_STATE.md` created.
- [ ] `CHANGELOG_IMPLEMENTATION.md` created.
- [ ] `KNOWN_LIMITATIONS.md` created.
- [ ] Dependency-ordered implementation plan approved/recorded.

**Exit evidence:** repository audit and gap report.

## Phase 1 — Repository and development foundation

- [ ] Monorepo structure established without overwriting existing work.
- [ ] Frontend starts locally.
- [ ] FastAPI starts locally.
- [ ] PostgreSQL/PostGIS starts and accepts connections.
- [ ] Redis starts and accepts connections.
- [ ] MinIO/private object storage starts locally.
- [ ] Docker Compose and environment example are documented.
- [ ] Health/readiness endpoints work.
- [ ] Lint, format, type-check and test commands are available.

**Exit evidence:** clean local startup and passing health checks.

## Phase 2 — Database, identity and tenant isolation

- [ ] SQLAlchemy models and Alembic migrations created.
- [ ] Organizations and users implemented.
- [ ] Authentication, logout and session/refresh lifecycle implemented.
- [ ] Roles and backend permission checks implemented.
- [ ] Organization context derived from authenticated principal.
- [ ] Tenant-aware relationships and constraints implemented.
- [ ] RLS/defence-in-depth implemented where specified.
- [ ] Two-organization test fixtures created.
- [ ] Cross-tenant direct-ID access tests pass.
- [ ] Role-permission tests pass.

**Exit evidence:** migrations and auth/security tests pass.

## Phase 3 — Domain registries and core APIs

- [ ] Department registry works.
- [ ] Contractor registry works.
- [ ] Infrastructure asset registry works.
- [ ] Contract registry works with validity dates/scope.
- [ ] Camera registry works.
- [ ] Responsibility lookup is deterministic and source-linked.
- [ ] Demo seed data is visibly labelled.
- [ ] CRUD, filter, pagination and tenant tests pass.

**Exit evidence:** registry APIs and matching tests pass.

## Phase 4 — Frontend design system and shells

- [ ] Dark Command Center layout completed.
- [ ] Light Admin Portal layout completed.
- [ ] Login/current-user integration completed.
- [ ] Navigation is role-aware.
- [ ] Shared components and design tokens exist.
- [ ] All required routes have a usable baseline.
- [ ] Loading, empty, error and permission states exist.
- [ ] No fake buttons or unlabelled mock metrics remain.
- [ ] Responsive and keyboard-accessible interactions checked.

**Exit evidence:** both interfaces connected to authentication and navigable.

## Phase 5 — Video upload and background jobs

- [ ] Private object-storage bucket configured.
- [ ] Authorized upload flow works.
- [ ] File type/size/content validation implemented.
- [ ] Video metadata stored in database.
- [ ] Celery/Redis processing jobs created.
- [ ] Job state/progress/retry/failure handling works.
- [ ] Frontend displays upload and job progress.
- [ ] Invalid, unsupported, oversized and corrupt files fail safely.

**Exit evidence:** upload-to-job workflow works end-to-end.

## Phase 6 — Computer vision and evidence

- [ ] Video decoder works on selected sample footage.
- [ ] Configurable frame sampler implemented.
- [ ] Detector adapter integrated.
- [ ] Supported vehicle/pedestrian classes documented.
- [ ] Tracker adapter integrated.
- [ ] Annotated frames/evidence generated.
- [ ] Timestamps and model/rule versions persisted.
- [ ] Worker failure and no-detection cases handled.
- [ ] Runtime and hardware limits documented.

**Exit evidence:** sample video processing produces stored detections/tracks/evidence.

## Phase 7 — Candidate events and human review

- [ ] Only validated event rules are enabled.
- [ ] Event rules are configurable/versioned.
- [ ] Candidate events include confidence and evidence timestamps.
- [ ] Near-miss and collision candidate are distinct.
- [ ] Unsupported event types show unavailable/manual-review state.
- [ ] Incident list and detail views work.
- [ ] Reviewer can confirm, reject or mark false positive.
- [ ] Review actions are audit logged.

**Exit evidence:** candidate-event review workflow passes tests.

## Phase 8 — GIS and hotspot analytics

- [ ] PostGIS location storage and spatial queries work.
- [ ] Historical accident data import works.
- [ ] Source and verification status are retained.
- [ ] Hotspot clustering/time aggregation works.
- [ ] Accident records and AI candidate events remain separate.
- [ ] Map endpoints return valid GeoJSON or documented equivalent.
- [ ] Map, list and hotspot detail views work.
- [ ] Exposure limitations are disclosed.
- [ ] Synthetic locations and statistics are labelled DEMO.

**Exit evidence:** geographic analysis reconciles with source records and tests.

## Phase 9 — Investigation and responsibility mapping

- [ ] Investigation can be created from reviewed event.
- [ ] Facts, hypotheses and missing information are separate.
- [ ] Asset matching is deterministic.
- [ ] Department mapping uses recorded ownership/maintenance data.
- [ ] Contract matching checks dates and scope.
- [ ] Contractor relationships cite source records.
- [ ] Ambiguous/missing records are shown honestly.
- [ ] Optional LLM output follows validated structured schema.
- [ ] LLM-offline/manual workflow works.
- [ ] No legal liability conclusions are generated.

**Exit evidence:** investigation displays traceable record matches and human review.

## Phase 10 — Recommendations and corrective-action workflow

- [ ] Recommendations include rationale and supporting evidence.
- [ ] Recommendation approval is human-controlled.
- [ ] Work orders can be created and assigned.
- [ ] Status transitions are validated server-side.
- [ ] Completion notes and evidence can be submitted.
- [ ] Verification is recorded.
- [ ] Separation of duties is enforced where configured.
- [ ] Audit timeline is available.
- [ ] Invalid transitions and unauthorized actions are tested.

**Exit evidence:** end-to-end work order and verification flow works.

## Phase 11 — Live CCTV adapter and simulated-live mode

- [ ] Server-side RTSP adapter exists.
- [ ] Trusted camera allowlist/configuration is enforced.
- [ ] RTSP disabled by default without authorized configuration.
- [ ] Credentials are never returned to browser/logs.
- [ ] Timeout/reconnect/backoff/shutdown handling exists.
- [ ] Simulated-live replay works.
- [ ] Simulated-live UI label is prominent.
- [ ] Real RTSP test is completed only with explicit authorization.

**Exit evidence:** adapter/mock tests pass; real RTSP status is honestly reported.

## Phase 12 — Real-time integration and dashboard polish

- [ ] Organization-scoped WebSocket authentication works.
- [ ] Job progress events arrive.
- [ ] Camera health events arrive where configured.
- [ ] Incident/review/work-order events arrive.
- [ ] Reconnect and stale-data state are visible.
- [ ] REST remains authoritative after reconnect.
- [ ] Dashboard values derive from API/database data.
- [ ] Metrics reconcile with backend records.

**Exit evidence:** multi-user real-time events are scoped and tested.

## Phase 13 — Security, privacy and reliability hardening

- [ ] Full endpoint authorization review completed.
- [ ] Cross-tenant tests pass.
- [ ] Role escalation tests pass.
- [ ] Upload/object-storage access reviewed.
- [ ] Secrets and logs reviewed for leakage.
- [ ] CORS/session/CSRF/rate-limit controls reviewed.
- [ ] Audit coverage reviewed.
- [ ] Retention/deletion policy documented.
- [ ] Backup/restore process documented and tested where possible.
- [ ] Dependency/security scans run where available.
- [ ] High-severity residual risks documented.

**Exit evidence:** security suite passes and residual risk register exists.

## Phase 14 — End-to-end QA and release candidate

- [ ] Clean-clone setup instructions verified.
- [ ] Migrations run from clean database.
- [ ] Unit tests pass.
- [ ] API/integration tests pass.
- [ ] UI tests pass where implemented.
- [ ] Tenant and permission tests pass.
- [ ] Demo flow completed from sign-in through verification.
- [ ] DEMO DATA and SIMULATED LIVE labels checked.
- [ ] Fallback demo recording/fixtures prepared.
- [ ] README and troubleshooting guide updated.
- [ ] Known limitations and production gaps published.
- [ ] Release-candidate checklist completed.

**Exit evidence:** reproducible demo and evidence-based release-candidate report.

---

# PART C — CONTINUE / RESUME COMMANDS

Use one of these short commands after the master prompt has been installed.

### Continue automatically

```text
Continue ROADGUARD AI from docs/IMPLEMENTATION_STATE.md. Inspect the actual
repository state, select the earliest incomplete dependency-ready phase, and
continue the implementation loop. Do not repeat completed work. Run the phase
gates and update all progress documents. Continue to the next phase whenever
the current phase passes. Stop only for a genuine blocker or a decision requiring
my authorization.
```

### Work only on one phase

```text
Work only on ROADGUARD AI Phase [NUMBER]. Inspect the repository and state file
first. Complete the phase gates, run the relevant tests, update documentation,
and do not begin the next phase until I review the result.
```

### Audit progress without coding

```text
Audit ROADGUARD AI against the phase checklist. Inspect code, tests, migrations
and runtime evidence. Do not modify files. Report each checklist item as
COMPLETE, IN PROGRESS, BLOCKED or NOT STARTED, with file/test evidence. Identify
false completion claims and recommend the next smallest task.
```

### Fix regressions

```text
Run a regression audit of ROADGUARD AI. Reproduce current failures, identify
root causes, fix only regressions, add tests, and verify the affected workflows.
Do not weaken security or acceptance criteria. Update the state and changelog.
```

---

# PART D — HUMAN RELEASE CHECK

Before presenting ROADGUARD AI as a completed hackathon prototype, the team lead should confirm:

- [ ] The complete workflow works on the actual demo environment.
- [ ] The demo uses authorized footage or clearly labelled sample footage.
- [ ] Synthetic data is not represented as real government data.
- [ ] Every AI finding is visibly marked as a candidate until reviewed.
- [ ] Department/contractor matching is backed by seeded or authorized records.
- [ ] No automated legal blame, penalties or autonomous signal control exists.
- [ ] Two different organizations cannot access each other's records.
- [ ] Work-order completion and verification are demonstrable.
- [ ] The team can explain current model limitations accurately.
- [ ] The final demo has a fallback if GPU, network, camera or LLM access fails.

**Completion principle:** A phase is complete because its code, evidence and tests satisfy its exit gate—not because the coding agent says it is done.
