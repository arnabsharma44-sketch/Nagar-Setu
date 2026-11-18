# Implementation Plan and Four-Person Team Work Breakdown

**Version:** 1.0  
**Planning basis:** 18-hour hackathon sprint; adjust to actual event duration.

## 1. Delivery strategy

Build one complete vertical slice before expanding feature breadth. The first slice is:

**Sign in → upload video → create background job → process sample → show evidence/event → review → create investigation → match demo asset records → create work order → verify completion.**

The Command Center and Admin Portal can be visually distinct but must call the same backend and permission model.

## 2. Team ownership

### Member 1 — Frontend/Product

Owns:
- Next.js App Router and design tokens.
- Command Center layout and routes.
- Admin Portal layout and routes.
- Video upload/job status UI.
- Incident evidence/review UI.
- Maps, tables, filters and responsive states.
- Typed API client and WebSocket UI integration.

Does not own:
- Backend permissions or data rules.
- Direct database calls.

### Member 2 — Backend/Database/Security

Owns:
- FastAPI app, configuration and middleware.
- PostgreSQL/PostGIS schema and Alembic migrations.
- Authentication, RBAC and tenant isolation.
- Camera/video/incident/asset/contract APIs.
- Investigation/work-order state transitions.
- Audit records and API documentation.

### Member 3 — Computer Vision/Worker

Owns:
- Video validation and FFmpeg/OpenCV decoding.
- YOLO detector adapter and class map.
- ByteTrack-compatible tracking integration.
- Frame sampling and event heuristics.
- Evidence frame/clip creation.
- Celery tasks, progress and failure handling.
- Model/version and rule-version metadata.

### Member 4 — GIS/Intelligence/Integration/QA

Owns:
- Seed data and import utilities.
- PostGIS hotspot query/DBSCAN analysis.
- Asset/department/contract responsibility matching logic with Member 2.
- LLM provider adapter and schema validation.
- End-to-end API/UI integration support.
- Test matrix, demo scenario and judge-facing metrics/limitations.

Member 4 must not invent an authority or contract relationship; those must originate in the seeded registry or an approved source record.

## 3. Shared integration contracts

Agree these before parallel coding:

1. UUID format and tenant ownership model.
2. `video.uploaded`, `job.status`, `incident.detected` data shapes.
3. Job status and progress semantics.
4. Incident type and review-status enumerations.
5. Storage-key/evidence model.
6. REST error envelope and pagination.
7. WebSocket event envelope.
8. Asset/contract responsibility response shape.

Create shared JSON schemas under `shared/schemas/` and review every breaking change in a short team sync.

## 4. 18-hour sequence

| Time | Shared milestone | Parallel work |
|---|---|---|
| 0–1 h | Repository, Docker, environment, architecture agreed | M1 shell; M2 database/app; M3 model smoke test; M4 fixtures/contracts |
| 1–3 h | Login, DB connection, API contract and upload shell | M1 auth/layout/upload UI; M2 auth/schema/upload API; M3 decoder + detector smoke test; M4 seed data + schema review |
| 3–6 h | Video reaches worker; job state visible | M1 job UI; M2 Celery/job APIs; M3 detection/tracking; M4 import and map base |
| 6–8 h | Events persisted and reviewable | M1 event detail; M2 incident/review APIs; M3 first event heuristic/evidence; M4 hotspot aggregate |
| 8–10 h | Investigation and asset matching | M1 investigation page; M2 asset/contract APIs; M3 event metadata quality; M4 responsibility rules |
| 10–12 h | Recommendations and assignment | M1 admin workflow; M2 investigation/work-order API; M3 worker reliability; M4 LLM schema and fallback |
| 12–14 h | Work-order completion/verification | M1 status timeline/forms; M2 transitions/audit; M3 processing fixes; M4 tests and demo script |
| 14–16 h | Integrated end-to-end flow | All fix integration failures and security tests |
| 16–17 h | Freeze scope and data | Test clean startup, backup demo clip and screenshots |
| 17–18 h | Final demo | Rehearse, record fallback demo, prepare limitations |

## 5. Integration cadence

- First 30–45 minutes: agree contracts and branch strategy.
- Every 60–90 minutes: merge small working changes to integration branch.
- Do not leave API integration until the end.
- Member 2 publishes OpenAPI as soon as endpoints exist.
- Member 3 publishes a mocked event payload before model integration finishes.
- Member 1 builds against the agreed API shape and temporary fixture data, then replaces it with real API responses.
- Member 4 maintains one shared end-to-end checklist and blocks false/unsupported claims in the demo.

## 6. Git workflow

- `main` must remain runnable.
- Use short-lived branches: `feat/auth`, `feat/video-upload`, `feat/cv-worker`, etc.
- Small commits with clear messages.
- Pull before starting work; avoid editing the same core files concurrently.
- PR/review for database migrations, auth/security and API contract changes.
- Never commit `.env`, model weights without licence review, real CCTV credentials or private footage.

## 7. Prioritization if time runs short

Keep, in this order:

1. Tenant-safe login and basic roles.
2. Upload video and show processing job.
3. Real detection/tracking output on sample footage.
4. At least one validated candidate event with evidence.
5. Human review.
6. Synthetic asset/department record match.
7. Investigation + work order + verification flow.
8. Map/hotspot visualization.
9. RTSP adapter and extra event types.
10. LLM-generated narrative polish.

A simulated live feed is acceptable if labelled. A disconnected live-video screen is not a substitute for a working uploaded-video pipeline.

## 8. Required handoff between members

- M3 → M2: job result schema, event payload, evidence metadata, failure codes.
- M2 → M1: OpenAPI URL, auth/session contract, pagination, status enums and role permissions.
- M2 + M4 → M1: responsibility endpoint and synthetic records.
- M4 → M2/M3: fixture clips, camera setup, expected event windows and dataset provenance.
- M1 → team: route list, UI state coverage and integration defects.

## 9. Final deliverables

- Running monorepo.
- README with verified setup steps.
- `.env.example`.
- Alembic migrations and idempotent seed script.
- OpenAPI documentation.
- Model/rule/version metadata.
- Unit/integration/e2e tests for key journeys.
- Synthetic demo video/data and source/usage note.
- Five-minute demo script and fallback recording.
- Known limitations and future-work list.
