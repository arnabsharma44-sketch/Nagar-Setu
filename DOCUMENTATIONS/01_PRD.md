# Product Requirements Document (PRD)

**Product:** ROADGUARD AI  
**Version:** 1.0  
**Status:** Approved baseline for hackathon prototype  
**Date:** 18 November 2026

## 1. Executive summary

ROADGUARD AI is a road-safety intelligence and corrective-action platform. It processes authorized traffic-camera footage and structured incident records to surface potential road-safety events and recurring risk locations. It connects a reviewed observation to infrastructure asset records, department responsibilities and maintenance-contract records, then supports a human-governed investigation and work-order workflow.

The platform has two web experiences sharing one backend:

- **Command Center:** operational monitoring, cameras, video jobs, potential events, map and investigations.
- **Administrative Portal:** departments, assets, contractors, contracts, assignments, work orders, verification, analytics and audit trail.

The MVP demonstrates the complete path from evidence ingestion to verified corrective-action tracking. It does not attempt to automate official findings of fault or legal liability.

## 2. Problem statement

Road-safety information can be distributed across camera footage, accident reports, road-asset registers, maintenance contracts and departmental workflows. A city may have difficulty turning these disconnected records into a traceable, proactive review process. ROADGUARD AI proposes a single workflow to organize evidence, highlight potential risks, retrieve relevant asset responsibility records and track follow-up action.

## 3. Product vision

**Turn authorized road-safety data into reviewable evidence, actionable investigations and traceable prevention work.**

Product promise: detect potential risk, help investigate the context, identify which authority's records should be reviewed, and track corrective action — with a human accountable for every official decision.

## 4. Goals and measurable outcomes

### MVP goals

1. Provide secure sign-in and role-based application access.
2. Upload a supported video and create an asynchronous processing job.
3. Run object detection and tracking on supported sample footage.
4. Produce at least one explainable potential event type on a validated demo clip, or clearly show that no event was detected.
5. Preserve source video, time offsets, model/rule versions and evidence references.
6. Show camera/event/asset coordinates on a map when location data exists.
7. Show historical accident records separately from AI-observed events.
8. Match an asset to seeded department and contract records without declaring liability.
9. Create and assign an investigation and work order.
10. Record completion evidence and a separate human verification decision.
11. Demonstrate organization and role isolation with automated tests.

### Success metrics for the demo

- 100% of uploaded demo files either complete processing or end in a visible, actionable failure state.
- Every generated event contains a source video, event timestamp or frame range, event type, rule/model version and review status.
- Every responsibility match exposes its source asset/contract record and is labelled as a record match, not a fault finding.
- Every work order has an assignee department, status history and completion/verification trail.
- No cross-organization record or WebSocket event is visible in isolation tests.
- A full demo scenario can be completed in approximately five minutes using seeded demo data.

## 5. Target users and personas

| Persona | Primary needs | Typical permissions |
|---|---|---|
| Platform administrator | Manage organizations, users, roles and configuration | Platform-level administration |
| Police/operations administrator | Register authorized cameras, inspect jobs/events, open investigations | Camera and incident operations |
| Traffic reviewer/officer | Review events and add operational observations | Assigned cameras/incidents |
| Department engineer | Review assigned infrastructure cases and update work | Assigned department cases/work orders |
| Municipal/department administrator | Manage department assets and work allocation | Department-scoped records |
| Auditor | Inspect records, decisions and change history | Read-only access to permitted records |

A user may hold more than one role only through an explicit authorization configuration. Role names alone do not grant cross-organization access.

## 6. Product scope

### P0 — Must ship in MVP

- Sign-in, sign-out, current-user endpoint and role-based authorization.
- Organization-scoped data model and server-side tenant enforcement.
- Command Center and Admin Portal route shells.
- Camera registry with location and connection status.
- Video upload using private object storage; file size/type validation.
- Background job creation, progress and failure reporting.
- YOLO-compatible object detection and tracker adapter.
- At least one validated event heuristic (for example, trajectory/proximity-based near-miss candidate) with thresholds in configuration.
- Incident/evidence review queue: confirm, reject as false positive, or mark needs more information.
- Historical accident records import from CSV/seed file, kept distinct from AI events.
- Hotspot visualization based on available, clearly typed data.
- Asset, department, contractor and contract registry using synthetic records.
- Investigation creation, notes/findings, evidence links and proposed recommendations.
- Work-order assignment, status transition and completion evidence.
- Human verification and append-only audit events for important actions.
- Demo seed script and one end-to-end demonstration flow.

### P1 — If time permits

- Authorized RTSP stream adapter behind a feature flag.
- Live job/event notifications using organization-scoped WebSockets.
- Additional validated event heuristics (wrong-way movement, sudden braking, pedestrian conflict) where camera setup supports them.
- GeoJSON hotspot endpoint and filters by time/event type/review state.
- CSV exports for permitted records.
- Department performance charts based on work-order data.

### P2 — Future scope, not part of MVP commitment

- Production integrations with police, municipal, road-owning authority or national accident databases.
- Broad citywide multi-camera deployment and high availability.
- Custom-trained accident/road-damage models with validated datasets.
- Calibrated speed measurement, crash reconstruction and automated signal-state interpretation.
- Signal control, traffic diversion or other autonomous physical actions.
- Facial recognition, person identification or automated number-plate recognition.
- Automated legal notices, fault findings, penalties or contractor blacklisting.
- Full digital twin or predictive accident-prevention simulation.
- Native mobile application.

## 7. Functional requirements

### FR-01 Identity and access

The system shall authenticate named users and derive user, organization, department and permissions from the server-side session. It shall reject unauthorized requests even when a user manually calls an API or changes a route URL.

### FR-02 Camera registry

Authorized users shall create and update camera metadata: name/code, organization, point location, description, source type and enabled state. Credentials must be stored as secret references, never returned by API. The MVP may show a simulated stream status when no real authorized stream is available.

### FR-03 Video ingestion

An authorized user shall upload supported video formats. The system shall validate content, enforce size/duration limits, store the file privately, create a video record and enqueue a processing job. The UI shall show queued, processing, succeeded or failed status.

### FR-04 AI processing

A worker shall decode the video, sample frames, run a configured detector, track objects when supported and apply versioned event rules. It shall store job metadata, processing status, detections/events and evidence references. Processing must be idempotent for a given job input and configuration.

### FR-05 Incident review

A reviewer shall inspect event metadata, video time range, annotated frames and confidence/limitations. A reviewer may confirm the event, reject it, or request more information. Reviewer identity and timestamp must be recorded.

### FR-06 Accident records and hotspots

The system shall import historical accident records with provenance and verification status. It shall not merge AI events and historical accident records into one indistinguishable count. Map and charts must identify the data source and filters used.

### FR-07 Infrastructure registry

Authorized administrators shall create road/infrastructure assets with unique organization-scoped asset codes, type, location, owning/maintaining department and condition status. A record's provenance and last-updated time should be visible.

### FR-08 Responsibility matching

The system shall retrieve department/contract relationships recorded for an asset, including effective contract dates and scope. The result shall be phrased as “records indicate” or “potentially relevant authority”, with a clear human-verification requirement. No automated liability conclusion is allowed.

### FR-09 Investigation

An authorized reviewer shall open an investigation linked to an incident and optionally an asset. An investigation shall store observed facts separately from hypotheses, missing information, assigned department, status, notes and evidence references.

### FR-10 Recommendations

The system may generate structured draft recommendations. Each recommendation shall include rationale, evidence references, priority, confidence/uncertainty and verification requirements. An authorized human must approve, edit or reject it before it becomes an approved action.

### FR-11 Work orders

An authorized user shall create a work order linked to an investigation and optionally an approved recommendation. Work orders shall have an assigned department, optional assignee, due date, status and history. Completion must be supported by submitted evidence and then separately verified by an authorized reviewer.

### FR-12 Auditability

The system shall record significant actions: sign-in/security events where appropriate, user/role changes, camera and asset changes, incident review, investigation assignment, recommendation approval/rejection, work-order transitions and verification decisions. Normal users must not edit or delete audit entries.

### FR-13 Notifications

The Command Center may receive job, camera and incident status events over organization-scoped WebSockets. All data must remain accessible via REST refresh so the UI is not dependent on a live socket.

## 8. Non-functional requirements

- **Security:** backend authorization, tenant isolation, private object storage, secret handling, input validation and audit trail.
- **Reliability:** a worker failure must not lose the job; failed jobs must show an error and be safely retryable.
- **Performance:** dashboard pages should load paginated data; video processing must not block API request workers.
- **Usability:** visible loading, empty, error and permission-denied states; keyboard-accessible controls; readable charts and status labels.
- **Maintainability:** typed API contracts, migrations, automated tests, structured logging and documented environment setup.
- **Explainability:** every AI-created event must reference source footage, timestamps, model/rule version and its limitations.
- **Privacy:** collect only data needed for the prototype; use synthetic data for demos; restrict raw video and apply retention rules.

## 9. Key user journeys

### Journey A — Uploaded footage to reviewed event

1. Operations user signs in.
2. User selects a registered camera or selects “unknown/unassigned source”.
3. User uploads video.
4. UI shows upload and processing state.
5. Worker analyses the file and creates potential events/evidence.
6. User opens an event, reviews the annotated frame and relevant clip.
7. User confirms, rejects or requests more information.

### Journey B — Reviewed event to investigation

1. Reviewer opens a confirmed event.
2. Reviewer starts an investigation.
3. System displays nearby assets and historical records with provenance and distance.
4. Reviewer selects the relevant asset or records that no asset match is established.
5. System displays associated department and contract records.
6. Reviewer reviews AI-generated draft hypotheses/recommendations.
7. Reviewer edits/approves a recommendation and assigns a department.

### Journey C — Work order to verified closure

1. Authorized user creates a work order.
2. Department user sees assigned work.
3. Department user updates progress and submits completion evidence.
4. A distinct authorized verifier reviews evidence.
5. Verifier accepts or rejects completion and records notes.
6. Work order and investigation status update according to workflow rules.
7. Audit trail records the transitions.

## 10. Assumptions and constraints

- The hackathon team has four developers and a short build window.
- A GPU may be available on one development machine, but the system must degrade gracefully to CPU or lower frame sampling.
- The team has no presumed permission to access actual police camera networks or official government databases.
- Seed data will be fictional and marked synthetic.
- A camera location may be missing or approximate; the application must not invent coordinates.
- The chosen YOLO weights and library must be used in accordance with their licence and documented in the repository.

## 11. Out of scope and product disclaimers

ROADGUARD AI does not determine legal fault, negligence, contractual breach or officer misconduct. It does not independently prove that a road defect caused an accident. It does not control traffic signals or issue government orders automatically. All findings are leads for authorized human review.

## 12. Release criteria

The MVP is ready for demonstration when the P0 requirements have a working end-to-end path, seeded demo data is clearly labelled, tenant/role tests pass, and the demo can be repeated from a clean local setup using the README.
