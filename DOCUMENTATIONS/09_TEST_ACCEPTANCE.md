# Test Plan and Acceptance Criteria

**Version:** 1.0  
**Status:** MVP release gate

## 1. Test strategy

Use a testing pyramid:

- Unit tests for business rules, validators, event heuristics and status transitions.
- API integration tests using an isolated test database and object-storage/queue substitutes where appropriate.
- Worker integration tests on small, licensed sample videos.
- Frontend component tests for key states and forms.
- Playwright end-to-end tests for the principal user journeys.
- Security tests for tenant isolation and permissions.
- Manual demo rehearsal on the actual presentation machine.

## 2. Test environments

- Unit: deterministic local test process.
- Integration: disposable PostgreSQL/PostGIS, Redis and object-storage test bucket or test doubles.
- E2E: full Docker Compose stack with synthetic seed data.
- Demo: frozen sample dataset and sample video clips; no real government data unless specifically authorized.

## 3. Functional acceptance tests

### A. Identity and authorization

| ID | Test | Expected result |
|---|---|---|
| AUTH-01 | Valid user signs in | Session established; current user returned |
| AUTH-02 | Invalid password | Generic authentication failure; no account data leaked |
| AUTH-03 | Disabled user signs in | Denied |
| AUTH-04 | Viewer attempts privileged action | 403/permission denial |
| AUTH-05 | User tampers with organization/role in request | Server ignores/rejects and uses authenticated principal |

### B. Upload and processing

| ID | Test | Expected result |
|---|---|---|
| VID-01 | Upload supported small MP4 | Private object created and metadata stored |
| VID-02 | Complete upload | File verified, job queued |
| VID-03 | Upload unsupported file | Rejected with actionable error |
| VID-04 | Upload exceeds configured limit | Rejected with 413 or equivalent |
| VID-05 | Worker processes valid sample | Job reaches succeeded and outputs are persisted |
| VID-06 | Corrupt video | Job reaches failed with safe error; no fabricated event |
| VID-07 | Retry transient failure | Job retries within configured limit and remains idempotent |
| VID-08 | Duplicate process request | No duplicate side effects for same idempotency key/config |

### C. AI and review

| ID | Test | Expected result |
|---|---|---|
| AI-01 | Detector runs on sample frame | Expected supported classes are returned with frame/time metadata |
| AI-02 | Tracker processes sequence | Track IDs are job-local and output is stable enough for demo clip |
| AI-03 | Event heuristic fires | Candidate event includes rule version, evidence time range and reasons |
| AI-04 | No heuristic conditions match | No event is fabricated |
| AI-05 | Reviewer confirms event | Reviewer/time/decision recorded |
| AI-06 | Reviewer rejects false positive | Status and notes recorded; event remains auditable |
| AI-07 | Reprocess with new version | New job/output version; old review record preserved |

### D. GIS and responsibility

| ID | Test | Expected result |
|---|---|---|
| GIS-01 | Valid coordinates imported | Correctly stored and plotted |
| GIS-02 | Invalid coordinates | Rejected or stored as unknown with explicit reason |
| GIS-03 | Historical accident map | Uses accident records only and labels source |
| GIS-04 | AI candidate layer | Separate from verified accident layer |
| GIS-05 | Nearby asset match | Shows match method/distance and source record |
| GIS-06 | Ambiguous/no asset match | Explicit ambiguous/no-match state; no guessed department |
| GIS-07 | Contract date outside event period | Not represented as an active contract for that period |

### E. Investigation and work order

| ID | Test | Expected result |
|---|---|---|
| FLOW-01 | Create investigation from incident | Linked case created and audit entry recorded |
| FLOW-02 | Generate LLM draft | Schema validated; hypotheses separated from facts |
| FLOW-03 | LLM unavailable | Manual investigation continues normally |
| FLOW-04 | Approve recommendation | Reviewer and approval time recorded |
| FLOW-05 | Create work order | Valid department assignment and status history |
| FLOW-06 | Submit completion evidence | Work order enters verification-pending state |
| FLOW-07 | Assignee tries to verify own work (when prohibited) | Denied |
| FLOW-08 | Verifier rejects completion | Notes recorded; work order can return for more evidence |
| FLOW-09 | Verifier accepts completion | Work order becomes verified; audit entry recorded |

### F. Tenant/security isolation

Create two organizations with separate users, departments, assets, cameras, videos, incidents, jobs and work orders. Attempt access through list, detail, search, update, download, export, background task and WebSocket. Every cross-tenant attempt must be denied or return a non-disclosing not-found response. Test pooled database connections to detect RLS context leakage.

## 4. End-to-end acceptance scenario

1. Sign in as demo police/operations user.
2. Upload the designated sample video and associate the DEMO camera.
3. Observe a queued/running/succeeded job state.
4. Open a generated candidate event and inspect evidence/timestamps.
5. Review the event and record a decision.
6. Open or create an investigation linked to the event.
7. View a nearby synthetic asset and associated department/contract records.
8. Review AI draft findings and missing evidence.
9. Approve a corrective recommendation.
10. Create and assign a work order.
11. Sign in as a department user and submit completion evidence.
12. Sign in as a permitted verifier and accept/reject the evidence.
13. Confirm audit timeline and work-order status.

## 5. AI quality evaluation

Select a small set of representative clips and manually inspect expected detections/events. Record observed false positives, misses, processing throughput and camera limitations. Do not state a general accuracy percentage unless a sufficiently sized labelled test dataset and a documented metric calculation support it.

## 6. Performance and resilience checks

- Confirm API remains responsive while worker processes video.
- Confirm a worker restart does not silently lose queued jobs.
- Confirm failed job displays safe error and is retryable only when eligible.
- Confirm UI handles API unavailable, Redis unavailable and socket reconnect states.
- Confirm large lists are paginated and do not load all records at once.
- Record sample video duration, machine CPU/GPU, processing time and frame-sampling settings in demo notes.

## 7. Definition of Done

A feature is done only when:

- It meets a documented requirement and has a real backend action.
- Loading, empty, error and permission-denied states exist.
- Backend validation and authorization exist.
- Relevant tests pass.
- Important changes are audited.
- Documentation and API contracts are updated.
- No secrets or real personal data are committed.

## 8. Release blocker list

Do not present the MVP as complete if any of these are true:

- Cross-tenant read/write/download is possible.
- A viewer can perform privileged actions.
- AI output is presented as a confirmed accident without review.
- A contractor/department/person is automatically declared liable.
- Demo data is presented as real city statistics.
- Camera credentials are exposed to the browser or logs.
- A work order can be closed without the configured verification process.
- The end-to-end demo cannot be repeated from a clean setup.
