# ROADGUARD AI — What This Website Does and How It Does It

## Executive Summary

ROADGUARD AI is a **government road-safety intelligence platform** that ingests CCTV footage, runs computer-vision detection to produce *candidate observations* (never legal findings), routes those candidates through a human review → investigation → corrective-work-order workflow with independent verification, and visualizes clusters of historical and AI-observed events on a map. It is built for municipal traffic departments, road-owning agencies, and their contractors.

**Current state:** A complete vertical slice that runs end-to-end on synthetic data with honest labelling. Real-world detection accuracy is unknown and unmeasured. No live RTSP feeds, no YOLO weights, no licensed detector benchmarked on labelled Indian CCTV data.

---

## SECTION 1 — Project Overview

### 1.1 Project Name
ROADGUARD AI

### 1.2 Product Description
A two-portal web application:
- **Command Center** (dark theme) — operational monitoring: camera registry, video upload, processing queue, incident review queue, evidence viewer, hotspot map, investigation management, live monitoring panel.
- **Administrative Portal** (light theme) — registry management: departments, contractors, infrastructure assets, contracts; investigation register; recommendations; work orders with completion evidence and independent verification; analytics; audit trail.
### 1.3 Main Objective
Give a city's traffic authority a single system where:
1. CCTV footage is uploaded to private object storage (never public).
2. A background worker runs detection/tracking and emits **candidate events** with annotated frames and clips.
3. A human reviewer confirms, rejects, or requests more information — every decision is audited.
4. Confirmed observations can be opened as **investigations** that deterministically match the event location to the nearest registered infrastructure asset, its owning department, and any maintenance contract active on the event date.
5. Root-cause hypotheses are drafted (deterministic rules; optional LLM adapter not exercised).
6. A recommendation is drafted, **independently approved**, then converted to a **work order**.
7. The responsible department completes the work, attaches evidence, and a **different user verifies** it.
8. Every consequential action is recorded in an **append-only audit log** at the database level.

### 1.4 Problem Statement
Municipal road-safety workflows today are fragmented:
- CCTV footage sits on local drives or proprietary VMS with no standard ingestion.
- No structured link between a detected near-miss and the asset/contract/department responsible for fixing it.
- Corrective actions are tracked in spreadsheets or paper; no separation of duties, no evidence trail.
- "Hotspot" maps mix police accident records with AI detections without source separation or exposure normalization.

### 1.5 Problems Being Addressed
| Problem | ROADGUARD AI Approach |
|---------|----------------------|
| Footage ingestion | Browser → signed URL → private MinIO/S3 → job row → background worker |
| Detection credibility | Every output labelled `CANDIDATE_OBSERVATION_NOT_CONFIRMED_EVENT`; human review mandatory |
| Responsibility lookup | Deterministic: event location → nearest asset (PostGIS) → owning department → contracts covering event date |
| Work-order integrity | State machine; completion evidence required; verifier ≠ completer; audit timeline |
| Hotspot honesty | DBSCAN clusters of *located* records; UI explicitly states "not an exposure-normalised risk rate" |
| Tenant isolation | Four-layer: JWT org context + composite FKs + transaction-local GUC + RLS policies |

### 1.6 Proposed Solution
A self-hosted stack (Docker Compose) with:
- **Frontend:** Next.js 16 (App Router), React 19, Tailwind v4, Leaflet maps.
- **Backend:** FastAPI, SQLAlchemy 2.0, PostgreSQL 16 + PostGIS, Redis, Celery.
- **AI Engine:** Synthetic-scene OpenCV detector (default, runs on CPU), optional YOLO adapter, IoU/ByteTrack tracking, six rule evaluators, evidence rendering (annotated frames + event clips via FFmpeg).
- **Storage:** MinIO (S3-compatible) or local filesystem; signed URLs only.
- **Auth:** Argon2id password hash, short-lived access JWT (15 min) + rotating refresh token in HttpOnly cookies, double-submit CSRF header, RBAC with 20+ permissions.

### 1.7 Target Users
| Role | Primary Portal | Key Permissions |
|------|----------------|-----------------|
| Operations Officer | Command Center | camera:read, video:upload, incident:read, incident:review, investigation:create, hotspot:analyze |
| Investigator | Command Center | investigation:read, investigation:analyze, recommendation:create, work_order:create |
| Department Engineer | Admin Portal | registry:read, registry:manage, work_order:read, work_order:complete, work_order:verify |
| Auditor | Admin Portal | audit:read, analytics:read (no write permissions) |
| Administrator | Both | user:manage, all registry permissions |

### 1.8 Intended Deployment Environment
- Self-hosted on-premises or in a government cloud tenancy.
- Docker Compose for development and single-server production.
- Kubernetes manifests not included (horizontal scale story: job claiming uses `FOR UPDATE SKIP LOCKED`, WebSocket hub has optional Redis pub/sub bridge).
- Supabase managed PostgreSQL supported via dual-role schema; bootstrap scripts ready.

### 1.9 Main Differentiators
1. **Honest AI labelling** — every detection is a "candidate," never an "accident."
2. **Deterministic responsibility chain** — asset → department → contract → contractor, all date-aware.
3. **Separation of duties enforced in code** — recommender ≠ approver; completer ≠ verifier.
4. **Append-only audit at DB level** — `UPDATE`/`DELETE` on `audit_logs` revoked from app role.
5. **Private storage by default** — no public URLs; signed tokens re-check tenant scope on download.
6. **No video in API requests** — uploads go direct to object storage; API only creates job rows.

### 1.10 Current Prototype Capabilities
- ✅ Full 12-step workflow executed (upload → job → detection → review → investigation → recommendation → approval → work order → completion → verification → audit).
- ✅ 23 frontend routes (9 Command Center, 12 Admin Portal, login, root redirect).
- ✅ 82 documented API operations across 69 paths; anonymous sweep passes.
- ✅ 61 pytest tests (38 unit + 23 integration) passing.
- ✅ TypeScript build passes; production Next.js build emits 24 routes.
- ✅ Docker Compose stack: postgres, redis, minio, api, worker, web all healthy.
- ❌ Real YOLO detection (BLOCKED — weights not installed).
- ❌ Real RTSP feed (BLOCKED — no authorised camera).
- ❌ Road-damage detection (NOT IMPLEMENTED).
- ❌ Automated UI/a11y/load tests (tooling not installed).

---

### 2.1 Authentication & Session Management
- **Feature:** Email/password sign-in, rotating refresh token, logout, CSRF protection
- **Purpose:** Secure, auditable access with short-lived credentials
- **Location:** `/login` (frontend), `POST /api/v1/auth/login`, `POST /api/v1/auth/refresh`, `POST /api/v1/auth/logout` (backend)
- **Database:** `users`, `refresh_sessions` (hash stored), `organizations`
- **Status:** FULLY IMPLEMENTED AND VERIFIED

### 2.2 Role-Based Access Control (RBAC)
- **Feature:** 20+ permissions mapped to 5 roles; enforced in FastAPI dependencies and PostgreSQL RLS
- **Purpose:** Ensure users only see/do what their role allows
- **Location:** `apps/api/app/core/permissions.py`, `apps/api/app/db/session.py` (RLS context)
- **Status:** FULLY IMPLEMENTED AND VERIFIED

### 2.3 Camera Registry
- **Feature:** Register cameras with code, name, source type (upload/simulated/RTSP-blocked), coordinates
- **Purpose:** Associate footage and events with known camera positions
- **Frontend:** `/command/cameras` (list + register form)
- **Backend:** `GET/POST /api/v1/cameras`, `POST /api/v1/cameras/{id}/enable|disable`, `POST /api/v1/cameras/{id}/live/simulate`
- **Database:** `cameras` table
- **Status:** FULLY IMPLEMENTED AND VERIFIED

### 2.4 Video Upload (Signed URL → Private Storage)
- **Feature:** Browser requests signed PUT URL → uploads directly to MinIO/S3 → confirms completion → job queued
- **Purpose:** Keep video out of API request/response; enforce size/duration/type limits
- **Frontend:** `/command/videos` (upload form + video list + job table)
- **Backend:** `POST /api/v1/videos/upload-url`, `POST /api/v1/videos/{id}/complete-upload`, `POST /api/v1/videos/{id}/process`
- **Storage:** `S3StorageBackend` or `LocalStorageBackend` (interface in `apps/api/app/services/storage.py`)
- **Status:** FULLY IMPLEMENTED AND VERIFIED

### 2.5 Background Job Processing
- **Feature:** Celery task + polling worker fallback; job leasing with `FOR UPDATE SKIP LOCKED`, attempt counting, retry limits
- **Purpose:** Run detection/tracking/evidence generation outside HTTP request lifecycle
- **Backend:** `ai_engine/workers/celery_app.py`, `ai_engine/workers/polling_worker.py`, `ai_engine/workers/runner.py`, `ai_engine/pipeline.py`
- **Database:** `jobs` table (status: queued → claimed → processing → succeeded/failed)
- **Status:** FULLY IMPLEMENTED AND VERIFIED
### 2.6 AI Detection & Tracking (Synthetic Scene)
- **Feature:** OpenCV colour-marker segmentation on generated clip → bounding boxes → IoU tracker → six rule evaluators
- **Purpose:** Produce candidate events with evidence for the demo without external model weights
- **Backend:** `ai_engine/detection/synthetic_scene.py`, `ai_engine/detection/yolo.py` (adapter, import-guarded), `ai_engine/tracking/tracker.py`, `ai_engine/events/*.py`
- **Output:** `incidents` rows with `source_kind=ai_detected`, `model_name=synthetic-scene-colour-marker`, limitation `SYNTHETIC_SCENE_DETECTOR`
- **Evidence:** Annotated frames (PNG), event clips (MP4 via FFmpeg)
- **Status:** IMPLEMENTED WITH SIMULATED DATA (synthetic detector only)

### 2.7 Six Event Rule Categories
| Rule | Input | Detection Logic | Status |
|------|-------|-----------------|--------|
| Near-miss | Track trajectories | Convergence + proximity threshold | EVALUATED |
| Collision candidate | Box overlap | Sustained IoU > threshold | EVALUATED |
| Pedestrian conflict | Pedestrian + vehicle tracks | Proximity + relative velocity | EVALUATED |
| Rapid motion | Track speed | Image-plane pixel velocity proxy | EVALUATED |
| Wrong-way | Track direction vs lane | Requires lane calibration → UNAVAILABLE | UNAVAILABLE |
| Signal violation | Track vs stop line | Requires stop-line mapping → UNAVAILABLE | UNAVAILABLE |

**Status:** IMPLEMENTED BUT PARTIALLY VERIFIED (only first 3 evaluated on synthetic clip)

### 2.8 Candidate Event Review
- **Feature:** Queue with filters (review status, event type, camera); detail page with evidence grid, detection metadata, reviewer actions (confirm/reject/needs-more-info)
- **Purpose:** Human-in-the-loop gate; every decision audited
- **Frontend:** `/command/incidents` (list), `/command/incidents/[id]` (detail + review)
- **Backend:** `GET /api/v1/incidents`, `GET /api/v1/incidents/{id}`, `GET /api/v1/incidents/{id}/evidence`, `PATCH /api/v1/incidents/{id}/review`
- **Database:** `incidents` (review_status: pending/confirmed/rejected_false_positive/needs_more_information)
- **Status:** FULLY IMPLEMENTED AND VERIFIED

### 2.9 Investigation & Responsibility Engine
- **Feature:** Open investigation from reviewed incident → deterministic asset match (PostGIS KNN) → department lookup → contract match (date range) → contractor list → hypotheses draft (deterministic or LLM)
- **Purpose:** Link observation to actionable responsibility records
- **Frontend:** `/command/investigations`, `/command/investigations/[id]`, `/admin/investigations`, `/admin/investigations/[id]`
- **Backend:** `POST /api/v1/investigations`, `GET /api/v1/investigations/{id}`, `POST /api/v1/investigations/{id}/analyze`
- **Database:** `investigations`, `investigation_hypotheses`, `assets`, `contracts`, `departments`, `contractors`
- **Status:** FULLY IMPLEMENTED AND VERIFIED

### 2.10 Recommendations & Independent Approval
- **Feature:** Draft recommendation → requires different user with `recommendation:approve` to approve/reject → self-approval rejected by server
- **Purpose:** Separation of duties for corrective actions
- **Frontend:** Investigation detail pages (both portals)
- **Backend:** `POST /api/v1/investigations/{id}/recommendations`, `PATCH /api/v1/recommendations/{id}/review`
- **Database:** `recommendations` (status: draft/approved/rejected)
- **Status:** FULLY IMPLEMENTED AND VERIFIED
### 2.11 Work Orders & Verification
- **Feature:** Create work order from approved recommendation (or directly) → state machine (pending → assigned → in_progress → completed_pending_verification → verified/rejected/needs_more_evidence) → completion evidence upload → independent verification
- **Purpose:** Track corrective work with evidence and separation of duties
- **Frontend:** `/admin/work-orders`, `/admin/work-orders/[id]`
- **Backend:** `POST /api/v1/work-orders`, `PATCH /api/v1/work-orders/{id}`, `POST /api/v1/work-orders/{id}/evidence`, `POST /api/v1/work-orders/{id}/completion`, `POST /api/v1/work-orders/{id}/verifications`
- **Database:** `work_orders`, `work_order_evidence`, `work_order_verifications`, `work_order_history`
- **Status:** FULLY IMPLEMENTED AND VERIFIED

### 2.12 Hotspot Analysis (DBSCAN)
- **Feature:** Run DBSCAN over geodesic distance on located records (AI confirmed + historical accidents) → clusters with centroid, counts by source/category, time window
- **Purpose:** Visualize concentrations of records; explicitly NOT a risk rate
- **Frontend:** `/command/hotspots`, `/admin/analytics` (map + cluster table)
- **Backend:** `POST /api/v1/hotspots/analyze`, `GET /api/v1/hotspots`, `GET /api/v1/hotspots/geojson`
- **Database:** `hotspot_analyses`, `hotspot_clusters`, `accident_records` (historical)
- **Status:** FULLY IMPLEMENTED AND VERIFIED

### 2.13 Historical Accident Import
- **Feature:** CSV import with provenance (`source_name`, `source_reference`, `verification_status` per row) → PostGIS geography + mirrored lat/lng columns
- **Purpose:** Reference layer for hotspots; never merged into AI counts
- **Backend:** `POST /api/v1/accident-records/import`, `GET /api/v1/accident-records`
- **Database:** `accident_records`
- **Status:** FULLY IMPLEMENTED AND VERIFIED

### 2.14 Real-time WebSocket Updates
- **Feature:** Ticket-authenticated WebSocket (60s single-use JWT) → broadcasts `incident.reviewed`, `job.status_changed`, etc. → clients refetch REST
- **Purpose:** Live dashboard updates without polling
- **Frontend:** `apps/web/lib/realtime.ts`, `useRealtime` hook
- **Backend:** `apps/api/app/api/v1/realtime.py`, `apps/api/app/services/realtime.py`
- **Status:** FULLY IMPLEMENTED AND VERIFIED (connection + ticket auth; broadcast delivery not asserted end-to-end)

### 2.15 Administrative Registries (CRUD)
- **Departments:** `/admin/departments` — owning authorities for assets
- **Contractors:** `/admin/contractors` — referenced by contracts
- **Assets:** `/admin/assets` — infrastructure with coordinates, type, condition, owning department
- **Contracts:** `/admin/contracts` — contractor + department + date range + asset list + scope
- **All:** List + create forms; server-side validation; demo data seeded
- **Status:** FULLY IMPLEMENTED AND VERIFIED
### 2.16 Analytics Dashboard
- **Feature:** Metric cards (total events, confirmed, pending, historical), event mix by type/review status, hotspot map, cluster table, historical accident table
- **Purpose:** Operational and administrative visibility
- **Frontend:** `/command` (dashboard), `/admin/analytics`
- **Backend:** `GET /api/v1/incidents/analytics`, `GET /api/v1/hotspots`, `GET /api/v1/accident-records`
- **Status:** FULLY IMPLEMENTED AND VERIFIED

### 2.17 Audit Trail
- **Feature:** Append-only `audit_logs` table; `UPDATE`/`DELETE` revoked from app role; trigger rejects non-owner writes; captured: actor, action, entity, summary, request_id
- **Purpose:** Tamper-evident record of every consequential action
- **Frontend:** `/admin/audit-logs`
- **Backend:** `GET /api/v1/audit-logs`, `apps/api/app/core/audit.py`
- **Database:** `audit_logs` (RLS + revoke + trigger)
- **Status:** FULLY IMPLEMENTED AND VERIFIED

---

## SECTION 3 — User Roles and Permissions

### 3.1 Configured Roles (from `apps/api/app/core/permissions.py`)
| Role | Description |
|------|-------------|
| `admin` | Full access within organization |
| `operations_officer` | Command Center operational tasks |
| `investigator` | Investigations, recommendations, work orders |
| `department_engineer` | Work order completion, asset/contract registry |
| `auditor` | Read-only analytics, audit logs, registries |

### 3.2 Permission Catalogue (20+ permissions)
```python
# From apps/api/app/core/permissions.py
PERMISSIONS = {
    # Auth
    "auth:login", "auth:refresh", "auth:logout",
    # Users
    "user:read", "user:manage",
    # Registry
    "registry:read", "registry:manage",
    # Cameras
    "camera:read", "camera:manage",
    # Videos
    "video:read", "video:upload", "video:process",
    # Incidents
    "incident:read", "incident:review",
    # Investigations
    "investigation:read", "investigation:analyze", "investigation:manage",
    # Recommendations
    "recommendation:create", "recommendation:approve",
    # Work orders
    "work_order:read", "work_order:create", "work_order:complete", "work_order:verify",
    # Analytics
    "analytics:read", "hotspot:analyze",
    # Audit
    "audit:read",
}
```

### 3.3 Role-Permission Matrix (derived from `ROLE_PERMISSIONS` in same file)

| Permission | admin | operations_officer | investigator | department_engineer | auditor |
|------------|-------|-------------------|--------------|---------------------|---------|
| auth:* | ✅ | ✅ | ✅ | ✅ | ✅ |
| user:read | ✅ | ❌ | ❌ | ❌ | ❌ |
| user:manage | ✅ | ❌ | ❌ | ❌ | ❌ |
| registry:read | ✅ | ✅ | ✅ | ✅ | ✅ |
| registry:manage | ✅ | ❌ | ❌ | ✅ | ❌ |
| camera:read | ✅ | ✅ | ✅ | ✅ | ✅ |
| camera:manage | ✅ | ✅ | ❌ | ❌ | ❌ |
| video:read | ✅ | ✅ | ✅ | ✅ | ✅ |
| video:upload | ✅ | ✅ | ❌ | ❌ | ❌ |
| video:process | ✅ | ✅ | ❌ | ❌ | ❌ |
| incident:read | ✅ | ✅ | ✅ | ✅ | ✅ |
| incident:review | ✅ | ✅ | ✅ | ❌ | ❌ |
| investigation:read | ✅ | ✅ | ✅ | ✅ | ✅ |
| investigation:analyze | ✅ | ❌ | ✅ | ❌ | ❌ |
| investigation:manage | ✅ | ❌ | ❌ | ❌ | ❌ |
| recommendation:create | ✅ | ❌ | ✅ | ❌ | ❌ |
| recommendation:approve | ✅ | ❌ | ❌ | ❌ | ❌ |
| work_order:read | ✅ | ✅ | ✅ | ✅ | ✅ |
| work_order:create | ✅ | ❌ | ✅ | ❌ | ❌ |
| work_order:complete | ✅ | ❌ | ❌ | ✅ | ❌ |
| work_order:verify | ✅ | ❌ | ❌ | ❌ | ❌ |
| analytics:read | ✅ | ✅ | ✅ | ✅ | ✅ |
| hotspot:analyze | ✅ | ✅ | ❌ | ❌ | ❌ |
| audit:read | ✅ | ❌ | ❌ | ❌ | ✅ |

### 3.4 Backend Authorization Implementation
- **FastAPI dependencies:** `require_permission(perm)` in `apps/api/app/core/permissions.py` — checks JWT `roles` claim.
- **RLS context:** Every request sets `SET LOCAL app.current_organization_id = $org_id` via `tenant_session` in `apps/api/app/db/session.py`.
- **Composite FKs:** All tenant tables have `(id, organization_id)` primary keys; foreign keys reference both columns.
- **Cross-tenant reads:** Return 404 (not 403) to avoid existence leakage — verified in `tests/integration/test_api_security.py`.

### 3.5 Organization/Department Isolation
- **Organization:** Top-level tenant boundary (users, cameras, videos, incidents, investigations, work orders, assets, contracts, departments, contractors all scoped to `organization_id`).
- **Department:** Sub-entity within organization; assets and contracts reference `department_id`; users can be assigned to a department.
- **No cross-organization data access** — enforced at DB (RLS) and API (permission deps) layers.
---

## SECTION 4 — Complete Frontend Walkthrough

### 4.1 Route Inventory (23 implemented routes)

#### Command Center (dark theme, `/command/**`)
| Route | Page Title | Purpose |
|-------|------------|---------|
| `/command` | Dashboard | Metrics: pending/confirmed/historical, cameras online, recent events, hotspot preview |
| `/command/cameras` | Camera Registry | Register cameras, toggle enable/disable, view connection status, coordinates |
| `/command/videos` | Videos & Processing Jobs | Upload footage (signed URL), view video list with validation status, job table with progress |
| `/command/incidents` | Event Review Queue | Filterable list of candidate events; link to detail |
| `/command/incidents/[id]` | Incident Detail | Evidence grid, detection metadata, human review actions (confirm/reject/needs-more-info) |
| `/command/monitoring` | Live Monitoring | Simulated-live panel (explicitly labelled); camera selector; session controls |
| `/command/hotspots` | Accident & Event Hotspots | Run DBSCAN analysis, view clusters on map + table, metrics cards |
| `/command/investigations` | Investigations List | Open cases with responsibility status, hypothesis count |
| `/command/investigations/[id]` | Investigation Detail | Record match, hypotheses, evidence, recommendations, work orders, nearby assets |

#### Administrative Portal (light theme, `/admin/**`)
| Route | Page Title | Purpose |
|-------|------------|---------|
| `/admin` | Administrative Portal Overview | Metric cards, corrective action pipeline, data quality gaps, recent audit actions |
| `/admin/departments` | Departments | Registry CRUD for owning authorities |
| `/admin/contractors` | Contractors | Registry CRUD for maintenance contractors |
| `/admin/assets` | Infrastructure Assets | Registry CRUD with coordinates, type, condition, department |
| `/admin/contracts` | Maintenance Contracts | Registry CRUD with contractor, department, date range, asset list |
| `/admin/investigations` | Case Register | Administrative view of all cases |
| `/admin/investigations/[id]` | Case Detail (Admin) | Record match, contracts, hypotheses, recommendations, work orders |
| `/admin/work-orders` | Corrective Work Orders | List with status metrics (awaiting verification, verified) |
| `/admin/work-orders/[id]` | Work Order Detail | State transitions, evidence upload, completion submission, independent verification |
| `/admin/analytics` | Analytics | Event mix, hotspot map, clusters, historical accident records |
| `/admin/audit-logs` | Audit Trail | Append-only log of consequential actions |
| `/admin/users` | Users & Roles | Invite users, assign roles/departments, enable/disable |

#### Auth & Root
| Route | Purpose |
|-------|---------|
| `/login` | Email/password sign-in; sets HttpOnly cookies |
| `/` | Redirects to `/command` if authenticated, else `/login` |

### 4.2 Key Reusable Components (`apps/web/components/`)
| Component | Purpose |
|-----------|---------|
| `AppShell.tsx` | Layout wrapper: sidebar nav, header with user/org, theme toggle (command/admin) |
| `ui.tsx` | 40+ primitives: Button, Card, DataTable, StatusBadge, PageHeader, Input, Select, Textarea, MetricCard, LoadingRows, ErrorState, PermissionNotice, EvidenceGrid, KeyValue, TagList, Row, Field, MapInner (Leaflet) |
| `EvidenceGrid.tsx` | Grid of evidence thumbnails (image/video/PDF) with signed URLs, type icons, download |
| `MapPanel.tsx` / `MapInner.tsx` | Leaflet map wrapper; points with layers (camera, incident, hotspot); popup details |
| `format.ts` | Formatters: date/time, coordinates, bytes, seconds, humanise (snake_case → Title Case) |
| `api.ts` | API client: `fetch` wrapper with CSRF header, cookie credentials, error envelope |
| `useApi.ts` | SWR-style hook: `useApi<T>(path)` → `{ data, loading, error, reload }` |
| `session.tsx` | React context: `useSession()` → `{ user, meta, has(perm), roles }` |
| `realtime.ts` | WebSocket hook: `useRealtime(onEvent)` — ticket auth, auto-reconnect |

### 4.3 State Management
- **Server state:** `useApi` hook (SWR-like) — caching, deduping, reload on mutation.
- **Session state:** React Context (`SessionProvider` in `AppShell`) — populated from `/api/v1/auth/me` on mount.
- **Form state:** Local `useState` + `FormData` (no form library).
- **URL state:** `useSearchParams` for filters (incidents page), dynamic route params for detail pages.

### 4.4 Authentication Handling
- **Login:** `POST /api/v1/auth/login` → sets `access_token` (15 min) + `refresh_token` (HttpOnly, Secure, SameSite=Lax).
- **Refresh:** `POST /api/v1/auth/refresh` (automatic via `api.ts` interceptor on 401) → rotates refresh token.
- **Logout:** `POST /api/v1/auth/logout` → revokes refresh session, clears cookies.
- **CSRF:** Double-submit cookie + header (`x-csrf-token`) on all unsafe methods; bootstrap endpoint `GET /api/v1/auth/csrf`.

### 4.5 WebSocket Integration
- **Ticket:** `GET /api/v1/realtime/ticket` → short-lived JWT (60s, single-use).
- **Connection:** `ws://host/api/v1/realtime/ws?ticket=...` → `useRealtime` hook in `AppShell`.
- **Events:** `incident.reviewed`, `job.status_changed`, `work_order.transitioned` — payload has `event_type` + ids only.
- **Client behavior:** On event → `useApi` reloads relevant queries.

### 4.6 Design Tokens (CSS Custom Properties in `apps/web/app/globals.css`)
```css
:root {
  --command-bg: #070d16;
  --command-panel: #0f1723;
  --command-panel-alt: #131e2c;
  --command-border: #1e2b3c;
  --command-accent: #38bdf8;
  --admin-bg: #f6f8fb;
  --admin-panel: #ffffff;
  --admin-border: #dfe6ee;
  --admin-accent: #1d4ed8;
  --focus: #f59e0b;
}
```
- **Command tone:** Dark navy/charcoal surfaces, sky accent.
- **Admin tone:** White/neutral surfaces, blue accent.
- **Shared:** Focus ring, reduced-motion media query, Leaflet container height fix.
---

## SECTION 5 — Command Center Explanation

### 5.1 Dashboard (`/command`)
- **Metrics cards:** Pending candidates, confirmed observations, historical accidents, cameras online (uses `connection_status === "online"`, fixed B-002).
- **Recent events table:** Top 5 pending + confirmed incidents with type, score, camera, time.
- **Hotspot preview:** Latest analysis clusters on mini map.
- **Data source:** `GET /api/v1/incidents/analytics`, `GET /api/v1/cameras`, `GET /api/v1/hotspots?limit=1`.

### 5.2 Camera Registry (`/command/cameras`)
- **List:** Code, name, source type, connection status (badge), coordinates, last seen, enabled toggle.
- **Register form:** Camera code, name, source type (upload_association / simulated_live / rtsp-blocked), description, lat/lng.
- **Monitor link:** Opens `/command/monitoring?camera=<id>`.
- **Backend:** `CameraService` in `apps/api/app/services/cameras.py`.

### 5.3 Video Upload (`/command/videos`)
- **Upload form:** File input (accepts mp4/mov/mkv), optional camera association.
- **Flow:** Request signed URL → PUT to MinIO → confirm upload → queue processing job.
- **Video table:** Filename, status (uploaded/processing/validated/failed), duration, size, upload time, validation error.
- **Job table:** Job ID, video ID, status, stage, progress %, model, event count, completed time.
- **Limits:** `MAX_UPLOAD_BYTES` (default 200 MB), `MAX_VIDEO_DURATION_SECONDS` (default 600s), `SUPPORTED_CONTENT_TYPES`.

### 5.4 Incident Review Queue (`/command/incidents`)
- **Filters:** Review status (pending/confirmed/rejected/needs_more_info), event type (6 AI types + manual), camera.
- **Table:** Event type + source badge, review status badge, model score, time window, camera, event time, reason codes, Review link.
- **Pending count badge** in header.

### 5.5 Incident Detail (`/command/incidents/[id]`)
- **Evidence grid:** Annotated frames, event clips (signed URLs, play in modal).
- **Detection details:** Source kind, model/version, rule/version, score, event time, window, camera, coordinates, reason codes, limitations, track IDs, raw features JSON.
- **Human review panel:** Reviewer notes textarea + three decision buttons (Confirm / Reject false positive / Needs more info) — only for `incident:review` permission.
- **Responsible use notice:** "A confirmed observation is not an accident determination or a liability finding."
### 5.6 Live Monitoring (`/command/monitoring`)
- **Camera list:** Sidebar with connection status badges.
- **Simulated stream panel:** Grid background, "SIMULATED LIVE" badge, elapsed timer, explicit disclaimer.
- **Start/Stop controls:** Call `POST /api/v1/cameras/{id}/live/simulate` and `/live/stop`.
- **No real RTSP** — adapter reports BLOCKED; simulated mode only.

### 5.7 Hotspots (`/command/hotspots`)
- **Run analysis form:** Radius (25–5000m), min records per cluster (2–50).
- **Map:** Cluster centroids with popups (label, counts by source/category).
- **Metric cards:** Clusters, total records, historical accidents, confirmed observations.
- **Cluster table:** Label, coordinates, total records, source mix, categories, first/last seen.
- **Methodology note:** "Clusters combine located records; they are not exposure-normalised risk rates."

### 5.8 Investigations (`/command/investigations` + detail)
- **List:** Case number, title, status, responsibility status, hypothesis count, updated time.
- **Detail:** Record match (asset, department, contracts, distance, match method, missing records, conflicts), hypotheses (deterministic or LLM draft), case evidence, recommendations (draft/approve/reject), work orders (create/view), nearby assets.

---

## SECTION 6 — Administrative Portal Explanation

### 6.1 Overview (`/admin`)
- **Metric cards:** Departments, assets (with/without department), contractors/contracts, open work orders (awaiting verification highlighted).
- **Corrective action pipeline:** Recent work orders with status, department, priority, due date.
- **Data quality gaps:** Assets without coordinates, assets without department, contracts with no assets, open investigations, pending candidates.
- **Recent audit actions:** Last 8 audit entries.

### 6.2 Registry Management (Departments, Contractors, Assets, Contracts)
Each follows same pattern:
- **List page:** DataTable with create button (if `registry:manage`).
- **Create form:** Validated fields; dropdowns for foreign keys (departments, contractors, assets).
- **Contracts form:** Multi-select for covered assets (checkbox list).
- **All tables:** Show `is_demo` badge for seeded data.

### 6.3 Investigations Register (`/admin/investigations` + detail)
- **List:** Case number, title, status, responsibility status, analysis source, updated.
- **Detail (read-only):** Record match, contract coverage, hypotheses, recommendations + work orders (links to admin work order detail).

### 6.4 Work Orders (`/admin/work-orders` + detail)
- **List:** Metrics (total, awaiting verification, verified), table with WO number, title, department, status, priority, due, completed.
- **Detail:** Work details, evidence grid, status history (audit timeline), allowed transitions (buttons), completion submission (evidence checkboxes + notes), verification panel (accept/request more/reject) — only for `work_order:verify` and separation of duties enforced.

### 6.5 Analytics (`/admin/analytics`)
- **Metric cards:** All events, confirmed, pending, historical records.
- **Event mix:** By review status + by event type (from `/api/v1/incidents/analytics`).
- **Hotspot map:** Latest analysis clusters.
- **Cluster table:** Same as command hotspots.
- **Historical accident records table:** Date, road, type, severity, source, verification status.

### 6.6 Audit Logs (`/admin/audit-logs`)
- **Table:** When, actor, action, entity, summary, request ID (truncated).
- **Immutability:** Enforced at DB level (revoke + trigger).

### 6.7 Users (`/admin/users`)
- **Invite form:** Full name, email, role (dropdown from server permission catalogue), department (optional), initial password (min 12 chars).
- **Table:** Name, email, role, department, state (active/disabled), last sign-in, enable/disable toggle.
---

## SECTION 7 — Frontend Technical Architecture

### 7.1 Next.js Application Structure
```
apps/web/
├── app/
│   ├── layout.tsx          # Root layout: SessionProvider, Toaster, global styles
│   ├── page.tsx            # Redirect to /command or /login
│   ├── login/page.tsx      # Sign-in form
│   ├── command/
│   │   ├── layout.tsx      # Command tone AppShell
│   │   ├── page.tsx        # Dashboard
│   │   ├── cameras/page.tsx
│   │   ├── videos/page.tsx
│   │   ├── incidents/page.tsx
│   │   ├── incidents/[id]/page.tsx
│   │   ├── monitoring/page.tsx
│   │   ├── hotspots/page.tsx
│   │   ├── investigations/page.tsx
│   │   └── investigations/[id]/page.tsx
│   └── admin/
│       ├── layout.tsx      # Admin tone AppShell
│       ├── page.tsx        # Overview
│       ├── departments/page.tsx
│       ├── contractors/page.tsx
│       ├── assets/page.tsx
│       ├── contracts/page.tsx
│       ├── investigations/page.tsx
│       ├── investigations/[id]/page.tsx
│       ├── work-orders/page.tsx
│       ├── work-orders/[id]/page.tsx
│       ├── analytics/page.tsx
│       ├── audit-logs/page.tsx
│       └── users/page.tsx
├── components/
│   ├── AppShell.tsx        # Sidebar, header, theme, realtime connection
│   ├── ui.tsx              # 40+ primitives
│   ├── EvidenceGrid.tsx
│   ├── MapPanel.tsx
│   └── MapInner.tsx
├── lib/
│   ├── api.ts              # Fetch wrapper + CSRF + error envelope
│   ├── useApi.ts           # SWR-like data hook
│   ├── session.tsx         # React Context + useSession()
│   ├── realtime.ts         # WebSocket hook + ticket auth
│   ├── format.ts           # Formatters
│   └── types.ts            # TypeScript interfaces for all API responses
├── globals.css             # Tailwind v4 + design tokens
├── next.config.ts          # API proxy rewrite + security headers
├── tsconfig.json
├── package.json
└── postcss.config.mjs
```

### 7.2 Key Technical Decisions
- **App Router only** — no route handlers; all API via proxy rewrite.
- **Proxy rewrite** (`next.config.ts`): `/api/:path*` → `http://api:8000/api/:path*` (internal Docker network).
- **No client-side tokens** — cookies are HttpOnly; CSRF via header.
- **SWR-like `useApi`** — keyed by path; dedupes requests; `reload()` for mutations.
- **Permission guard:** `useSession().has("perm")` → renders `PermissionNotice` component.
- **Loading/Empty/Error states:** Built into `useApi` + `LoadingRows`, `ErrorState`, `DataTable` empty prop.
- **Map:** Leaflet + React Leaflet; `MapInner` renders points with layer-specific markers/popups.
---

## SECTION 8 — Backend Technical Architecture

### 8.1 FastAPI Application Structure
```
apps/api/app/
├── main.py                 # FastAPI app, lifespan, middleware, router inclusion
├── core/
│   ├── config.py           # Pydantic Settings (env vars)
│   ├── security.py         # JWT, Argon2, CSRF, rate limiter
│   ├── permissions.py      # Permission catalogue + RBAC deps
│   ├── audit.py            # Audit log helper
│   ├── errors.py           # Exception handlers + ProblemDetail envelope
│   └── ratelimit.py        # SlidingWindowLimiter (in-process)
├── db/
│   ├── session.py          # Engine, sessionmakers, tenant_session, RLS context
│   ├── base.py             # Declarative base + naming conventions
│   ├── urls.py             # Supabase URL normalization
│   └── _types.py           # PostGIS Geography, UUID, TSVector
├── models/
│   ├── __init__.py         # Exports all models
│   ├── enums.py            # SQLEnums for all status/type fields
│   ├── identity.py         # User, Organization, RefreshSession, Role
│   ├── registry.py         # Department, Contractor, Asset, Contract, Camera
│   ├── media.py            # Video, Job, Evidence
│   ├── incidents.py        # Incident, IncidentEvidence
│   └── workflow.py         # Investigation, Hypothesis, Recommendation, WorkOrder, WorkOrderEvidence, Verification, History, HotspotAnalysis, HotspotCluster, AccidentRecord, AuditLog
├── schemas/
│   ├── common.py           # Envelope, Pagination, ProblemDetail
│   ├── domain.py           # Request/Response models per domain
│   └── serializers.py      # ORM → Pydantic conversion
├── services/
│   ├── identity.py         # Auth, users, sessions
│   ├── registry.py         # Departments, contractors, assets, contracts
│   ├── cameras.py          # Camera registry + simulated live
│   ├── videos.py           # Upload URL, validation, job creation
│   ├── media_validation.py # FFprobe validation
│   ├── storage.py          # Local/S3 backend interface
│   ├── incidents.py        # Incident CRUD, review, evidence
│   ├── analytics.py        # Analytics, hotspots, accident import
│   ├── investigations.py   # Investigation, analysis, responsibility match
│   ├── work_orders.py      # Work order lifecycle, evidence, verification
│   ├── geo.py              # PostGIS helpers
│   └── events.py           # Realtime event publishing
├── api/v1/
│   ├── __init__.py         # Router aggregation + OpenAPI tags
│   ├── auth.py             # Login, refresh, logout, me, csrf
│   ├── cameras.py
│   ├── videos.py
│   ├── incidents.py
│   ├── investigations.py
│   ├── work_orders.py
│   ├── registry.py         # Departments, contractors, assets, contracts
│   ├── accidents.py
│   ├── audit.py
│   ├── realtime.py         # Ticket + WebSocket
│   └── storage.py          # Signed URL generation
└── alembic/                # 3 migrations
```

### 8.2 API Versioning & Router Aggregation
- **Prefix:** `/api/v1` (all routers).
- **Tags:** `auth`, `cameras`, `videos`, `incidents`, `investigations`, `work-orders`, `registry`, `accidents`, `audit`, `realtime`, `storage`.
- **OpenAPI:** Generated at `/openapi.json`; used by endpoint coverage test.

### 8.3 Dependency Injection
- **Database:** `get_db` (privileged owner session for migrations/seeding), `get_tenant_db` (RLS-enforced app session).
- **Auth:** `get_current_user` → `UserPrincipal` (id, email, roles, organization_id).
- **Permissions:** `require_permission("perm")` → FastAPI dependency.
- **Storage:** `get_storage_backend` → `LocalStorageBackend` or `S3StorageBackend`.

### 8.4 Background Tasks
- **Celery:** `ai_engine/workers/celery_app.py` — Redis broker, task `process_ai_job`.
- **Polling worker:** `ai_engine/workers/polling_worker.py` — `claim_ai_job` (SECURITY DEFINER) + lease loop.
- **Shared pipeline:** `ai_engine/pipeline.py` — `process_job(job_id, db)` called by both paths.

### 8.5 Error Handling
- **ProblemDetail envelope** (RFC 9457): `type`, `title`, `status`, `detail`, `instance`.
- **Exception handlers:** Validation (422), HTTPException, SQLAlchemy integrity, generic 500.
- **Starlette deprecation warnings** for 422/413 constants (cosmetic).
---

## SECTION 9 — Database Architecture

### 9.1 Tables (25 total, 23 with RLS)
| Table | Purpose | RLS | Key Columns |
|-------|---------|-----|-------------|
| `organizations` | Tenant root | ✅ | id, name, created_at |
| `users` | App users | ✅ | id, org_id, email, password_hash, full_name, role, department_id, is_active |
| `refresh_sessions` | Rotating refresh tokens | ✅ | id, user_id, token_hash, expires_at, revoked_at |
| `departments` | Owning authorities | ✅ | id, org_id, name, type, contact_email, source_reference |
| `contractors` | Maintenance contractors | ✅ | id, org_id, name, registration_number, contact_email, source_reference |
| `assets` | Infrastructure assets | ✅ | id, org_id, asset_code, name, type, address, department_id, location (geog), condition_status, source_reference |
| `contracts` | Maintenance contracts | ✅ | id, org_id, contractor_id, department_id, contract_number, type, scope, start_date, end_date, warranty_end_date, asset_ids[], source_reference |
| `cameras` | CCTV cameras | ✅ | id, org_id, camera_code, name, description, source_type, location (geog), is_enabled, connection_status, last_seen_at |
| `videos` | Uploaded footage metadata | ✅ | id, org_id, camera_id, original_filename, storage_key, file_size_bytes, duration_seconds, status, validation_error, recorded_at, source_type |
| `jobs` | AI processing jobs | ✅ | id, org_id, video_id, status, stage, progress, model_name, model_version, result_summary, attempts, lease_expires_at, idempotency_key |
| `evidence` | Evidence artefacts (frames, clips, photos) | ✅ | id, org_id, job_id, incident_id, work_order_id, evidence_type, storage_key, file_size_bytes, checksum_sha256, label, created_at |
| `incidents` | Candidate events + manual reports | ✅ | id, org_id, job_id, camera_id, incident_type, source_kind, model_name, model_version, rule_name, rule_version, model_score, review_status, reviewed_at, review_notes, review_by, event_time, start/end_offset_seconds, location (geog), reason_codes[], limitations[], track_ids[], features (JSONB) |
| `investigations` | Cases | ✅ | id, org_id, incident_id, case_number, title, summary, status, responsibility_status, analysis_source, hypotheses (JSONB), created_by |
| `investigation_hypotheses` | Root-cause hypotheses | ✅ | id, investigation_id, hypothesis, confidence_label, supporting_record_ids[], counter_evidence[] |
| `recommendations` | Corrective recommendations | ✅ | id, org_id, investigation_id, recommendation_text, rationale, priority, status, created_by, approved_by, approved_at, limitations[] |
| `work_orders` | Actionable work orders | ✅ | id, org_id, investigation_id, recommendation_id, assigned_department_id, work_order_number, title, description, priority, due_date, status, separation_of_duties, completed_at, verified_at |
| `work_order_evidence` | Completion evidence | ✅ | id, work_order_id, evidence_id |
| `work_order_verifications` | Independent verifications | ✅ | id, work_order_id, verifier_id, verification_status, notes, verified_at |
| `work_order_history` | State transition audit | ✅ | id, work_order_id, from_status, to_status, note, created_by |
| `hotspot_analyses` | DBSCAN analysis runs | ✅ | id, org_id, method, radius_meters, min_size, window_from, window_to, data_sources[], unlocated_count, generated_at, methodology_note |
| `hotspot_clusters` | Clusters within analysis | ✅ | id, analysis_id, cluster_key, latitude, longitude, total_records, counts (JSONB), categories (JSONB), source_mix[], first_seen, last_seen, label |
| `accident_records` | Historical CSV imports | ✅ | id, org_id, accident_time, accident_date, road_name, accident_type, severity, latitude, longitude, location (geog), source_name, source_reference, verification_status |
| `audit_logs` | Append-only action log | ✅ (revoke + trigger) | id, org_id, actor_id, actor_label, action, entity_type, entity_id, summary, request_id, created_at |

### 9.2 Key Relationships (Composite FKs)
- All tenant tables: `(id, organization_id)` PK.
- FKs reference both columns: e.g., `videos(organization_id, camera_id) → cameras(organization_id, id)`.
- **Assets → Departments:** `assets(department_id, organization_id) → departments(id, organization_id)`.
- **Contracts → Assets:** `contract_assets` join table with composite FKs.
- **Investigations → Incidents:** `investigations(incident_id, organization_id) → incidents(id, organization_id)`.
- **Work Orders → Investigations:** `work_orders(investigation_id, organization_id) → investigations(id, organization_id)`.

### 9.3 PostGIS Usage
- **Geography type:** `location` columns use `Geography(POINT, 4326)` for geodesic distance.
- **Mirrored lat/lng:** Separate `latitude`/`longitude` numeric columns for map serialization (migration `837c7ef69730`).
- **KNN match:** `assets.location <-> ST_SetSRID(ST_MakePoint(lng, lat), 4326)::geography` for nearest asset.
- **DBSCAN:** Custom SQL function `dbscan_clusters(radius_m, min_size)` using `ST_DWithin` on geography.

### 9.4 Audit Log Design
- **Append-only:** `REVOKE UPDATE, DELETE ON audit_logs FROM roadguard_app`.
- **Trigger:** `audit_log_immutability_trigger` rejects non-owner writes.
- **Captured:** Actor (user/system), action (enum), entity type/id, summary, request_id (for correlation).

### 9.5 Migration History
| Revision | Description |
|----------|-------------|
| `a0f8b507499d` | Initial RoadGuard schema (all tables, enums, FKs, RLS policies) |
| `b1c2d3e4f5a6` | Security layer: refresh_sessions, audit_log revoke/trigger, rate limiter, composite FKs |
| `837c7ef69730` | Coordinate columns for map serialization (lat/lng on assets, cameras, incidents, accident_records) |
---

## SECTION 10 — AI and Computer Vision Architecture

### 10.1 Video Ingestion & Frame Extraction
- **Decoder:** `ai_engine/video/decoder.py` — `VideoDecoder` (OpenCV) extracts frames at configurable stride.
- **Sampling:** Default 1 fps for 12s clip → 12 frames; configurable via `FRAME_SAMPLE_RATE`.
- **Validation:** `media_validation.py` uses `ffprobe` to verify codec, duration, resolution before job creation.

### 10.2 Detector Adapters
| Adapter | File | Status | Model Label | Limitations Tag |
|---------|------|--------|-------------|-----------------|
| Synthetic Scene | `detection/synthetic_scene.py` | DEFAULT, VERIFIED | `synthetic-scene-colour-marker` v`synthetic_scene_v1` | `SYNTHETIC_SCENE_DETECTOR` |
| YOLO | `detection/yolo.py` | ADAPTER ONLY, BLOCKED | `yolov8*` (configurable) | `YOLO_DETECTOR` (would be added) |

**Synthetic detector logic:** Generates colour-marker overlays on frames; segments by HSV colour ranges → bounding boxes. Produces deterministic tracks for the demo clip.

### 10.3 Tracking
- **IoU Tracker (default):** `tracking/tracker.py` — `IouTracker` associates detections frame-to-frame by IoU > 0.3; assigns job-local track IDs.
- **ByteTrack adapter:** `tracking/bytetrack.py` — optional dependency, not exercised.

### 10.4 Event Rules (6 Categories)
All rules in `ai_engine/events/*.py` inherit `EventRule` base class:
```python
class EventRule:
    def evaluate(self, tracks: list[Track], frame_shape: tuple, fps: float) -> list[EventCandidate]:
        ...
```
Each returns `EventCandidate` with:
- `incident_type` (e.g., `near_miss_candidate`)
- `rule_name`, `rule_version`
- `model_score` (0–1 heuristic)
- `start_offset_seconds`, `end_offset_seconds`
- `track_ids`, `features` (JSON)
- `reason_codes[]`, `limitations[]`
- `status`: `"evaluated"` or `"unavailable"` (with note)

**Rule details:**
1. **NearMissRule** — Converging trajectories + proximity < threshold → score from inverse distance.
2. **CollisionCandidateRule** — Sustained box overlap (IoU > 0.5 for N frames) → score from overlap duration.
3. **PedestrianConflictRule** — Pedestrian track + vehicle track proximity + relative velocity.
4. **RapidMotionRule** — Image-plane speed proxy (pixels/sec normalized by box size).
5. **WrongWayRule** — Requires lane direction calibration → returns `unavailable`.
6. **SignalViolationRule** — Requires stop-line mapping → returns `unavailable`.

### 10.5 Evidence Generation
- **Annotated frames:** `video/evidence.py` — draws boxes, track IDs, event zones on frame → PNG.
- **Event clips:** `video/evidence.py` — FFmpeg extracts `[start-1s, end+1s]` → MP4 (H.264).
- **Storage:** Uploaded to MinIO via storage backend; `evidence` rows created with checksums.

### 10.6 Pipeline Orchestration
`pipeline.py` — `process_job(job_id, db)`:
1. Claim job (lease), update status → `processing`.
2. Download video from storage to temp file.
3. Decode frames → detector → tracker.
4. Run all 6 rules → collect candidates.
5. For each candidate: create `incident` row + evidence artefacts.
6. Update job `result_summary` (event_count, detection_count, processing_time_ms).
7. Mark job `succeeded` or `failed` with `validation_error`.
8. Publish realtime events (`job.status_changed`, `incident.created`).

### 10.7 CPU/GPU Handling
- **Synthetic detector:** Pure OpenCV (CPU), no dependencies.
- **YOLO adapter:** Would use `torch` + `ultralytics`; `CUDA_VISIBLE_DEVICES` respected; falls back to CPU.
- **No GPU in current environment** — synthetic detector only.
---

## SECTION 11 — Dataset Integration

### 11.1 Integrated Datasets
| Dataset | Source | License | Status | Local Path |
|---------|--------|---------|--------|------------|
| Synthetic demo clip | `scripts/generate_demo_clip.py` | Project-generated | VERIFIED | `datasets/sample_videos/demo_intersection_synthetic.mp4` |
| Historical accidents fixture | `datasets/sample_accidents/demo_accidents.csv` | Project fixture | VERIFIED | 8 records, seeded via `seed_database.py` |

### 11.2 External Datasets (BLOCKED — Not Acquired)
| Dataset | Camera Type | Access Issue | Manual Steps |
|---------|-------------|--------------|--------------|
| AI City Challenge 2020 Track 4 | Fixed highway CCTV | Google Drive interstitial, no bytes | Download 10.7 GB manually, place in `datasets/incoming/` |
| RDD2022 India | Road damage | S3 403 Forbidden | Request access, download to `datasets/incoming/` |
| BDD100K | Dashcam | Login/licence wall | Accept licence, download to `datasets/incoming/` |

**Tooling ready:** `scripts/prepare_dataset.py` validates, hashes, manifests, and can upload via API. `scripts/datasets/` has annotation parsers and evaluators.

### 11.3 Dataset Preparation Pipeline
```bash
# Validate incoming clips
python scripts/prepare_dataset.py --input datasets/incoming

# Upload and wait for processing
DEMO_SEED_PASSWORD=... python scripts/prepare_dataset.py \
  --input datasets/incoming --upload \
  --api-url http://localhost:8000 --email ops@demo.roadguard.ai --wait-seconds 300
```

---

## SECTION 12 — Hotspot and GIS Architecture

### 12.1 Coordinate Handling
- **Storage:** PostGIS `Geography(POINT, 4326)` + mirrored `latitude`/`longitude` numeric columns.
- **Sources:** Cameras (surveyed/approximate), Assets (surveyed), Incidents (from camera location), Accident records (CSV lat/lng).
- **Quality tag:** `location_quality` enum: `surveyed` / `approximate` / `derived`.

### 12.2 Spatial Queries
- **Nearest asset:** `ORDER BY assets.location <-> event_point::geography LIMIT 1`.
- **Match radius:** Configurable (default 50m); beyond → `no_asset_match`.
- **DBSCAN:** `ST_DWithin` on geography with radius in metres; `min_size` = minimum points per cluster.

### 12.3 Hotspot Analysis Flow
1. `POST /api/v1/hotspots/analyze` with radius, min_size, optional time window.
2. Service collects located records: confirmed incidents + historical accidents.
3. Runs `dbscan_clusters` SQL function → inserts `hotspot_analysis` + `hotspot_clusters`.
4. Returns analysis with clusters, methodology note, unlocated count.
5. Frontend renders GeoJSON on Leaflet map.

### 12.4 Source Separation
- **Never merged:** Historical accidents (`source_name`, `verification_status`) kept separate from AI candidates (`source_kind=ai_detected`).
- **Cluster `source_mix`:** Array like `["confirmed_observation", "historical_accident"]`.
- **UI disclaimer:** "Clusters combine located records; they are not exposure-normalised risk rates and do not establish causation."
---

## SECTION 13 — Investigation and Accountability Engine

### 13.1 Complete Process Flow
```
Incident (confirmed)
    → Investigation opened (case_number: INV-YYYY-NNNN)
    → Deterministic responsibility match:
        Event location → nearest asset (PostGIS KNN)
        → asset.owning_department
        → contracts where asset_id IN contract.asset_ids
           AND contract.start_date <= event_date <= contract.end_date
        → contractors from matched contracts
    → Record match result: status (matched_records / no_asset_match / requires_field_verification)
    → Hypotheses drafted:
        Deterministic: rule-based from event type + asset type + condition
        LLM (optional): structured JSON via adapter (NOT EXERCISED)
    → Human reviews hypotheses → drafts recommendation
    → Different user approves recommendation
    → Work order created → assigned to department
    → Department completes work → uploads evidence
    → Different user verifies completion
    → Audit trail records every step
```

### 13.2 Deterministic Responsibility Matching
- **Service:** `investigations.analyze_investigation()` in `apps/api/app/services/investigations.py`.
- **Output:** `InvestigationAnalysis` with `potential_root_causes`, `missing_information`, `limitations`, `potentially_relevant_authorities`.
- **Match method:** `nearest_asset_postgis` / `asset_coordinates_missing` / `asset_not_registered`.

### 13.3 Contract Matching
- **Date-aware:** Only contracts where `start_date <= event_date <= end_date` are `is_active_on_event_date = true`.
- **Scope notes:** Contract `scope_description` and `scope_notes` surfaced in UI.

### 13.4 Root-Cause Hypotheses
- **Structure:** `hypothesis` (string), `confidence_label` (low/medium/high), `supporting_record_ids[]`, `counter_evidence[]`.
- **Deterministic rules:** e.g., "Signal timing mismatch" for signal_violation + traffic_signal asset; "Inadequate sight distance" for near_miss + intersection asset with condition=poor.
- **LLM adapter:** `ai_engine/investigation/llm_analyzer.py` — validates strict JSON schema; `LLM_PROVIDER=none` by default.

### 13.5 Human Approval & Separation of Duties
- **Recommendation:** Author cannot approve (server rejects `created_by == approver_id`).
- **Work order:** Completer cannot verify (server checks `verifier_id != completed_by` via `separation_of_duties` flag).
- **All decisions:** Recorded in `audit_logs` with actor, action, entity, summary.

### 13.6 Legal Disclaimer
> **Record matches prove only that records exist and that a contract's date range covers the event date. They do not prove responsibility, liability, negligence, or fault.**
---

## SECTION 14 — Complete API Documentation

### 14.1 Auth
| Method | Path | Purpose | Auth | Roles |
|--------|------|---------|------|-------|
| POST | `/api/v1/auth/login` | Email/password → cookies | None | — |
| POST | `/api/v1/auth/refresh` | Rotate refresh token | Refresh cookie | — |
| POST | `/api/v1/auth/logout` | Revoke session, clear cookies | Access cookie | — |
| GET | `/api/v1/auth/me` | Current user + meta | Access cookie | — |
| GET | `/api/v1/auth/csrf` | Bootstrap CSRF cookie | None | — |

### 14.2 Cameras
| Method | Path | Purpose | Auth | Permission |
|--------|------|---------|------|------------|
| GET | `/api/v1/cameras` | List cameras | Access | camera:read |
| POST | `/api/v1/cameras` | Register camera | Access | camera:manage |
| POST | `/api/v1/cameras/{id}/enable` | Enable camera | Access | camera:manage |
| POST | `/api/v1/cameras/{id}/disable` | Disable camera | Access | camera:manage |
| POST | `/api/v1/cameras/{id}/live/simulate` | Start simulated session | Access | camera:manage |
| POST | `/api/v1/cameras/{id}/live/stop` | Stop simulated session | Access | camera:manage |

### 14.3 Videos & Jobs
| Method | Path | Purpose | Auth | Permission |
|--------|------|---------|------|------------|
| GET | `/api/v1/videos` | List videos | Access | video:read |
| POST | `/api/v1/videos/upload-url` | Get signed PUT URL | Access | video:upload |
| POST | `/api/v1/videos/{id}/complete-upload` | Confirm upload | Access | video:upload |
| POST | `/api/v1/videos/{id}/process` | Queue processing job | Access | video:process |
| GET | `/api/v1/jobs` | List jobs | Access | video:read |

### 14.4 Incidents
| Method | Path | Purpose | Auth | Permission |
|--------|------|---------|------|------------|
| GET | `/api/v1/incidents` | List with filters | Access | incident:read |
| GET | `/api/v1/incidents/{id}` | Detail | Access | incident:read |
| GET | `/api/v1/incidents/{id}/evidence` | Evidence artefacts | Access | incident:read |
| PATCH | `/api/v1/incidents/{id}/review` | Review decision | Access | incident:review |
| GET | `/api/v1/incidents/analytics` | Dashboard metrics | Access | analytics:read |

### 14.5 Investigations
| Method | Path | Purpose | Auth | Permission |
|--------|------|---------|------|------------|
| GET | `/api/v1/investigations` | List | Access | investigation:read |
| POST | `/api/v1/investigations` | Create from incident | Access | investigation:create |
| GET | `/api/v1/investigations/{id}` | Detail (with responsibility, hypotheses, recs, WOs) | Access | investigation:read |
| POST | `/api/v1/investigations/{id}/analyze` | Run deterministic/LLM analysis | Access | investigation:analyze |
| POST | `/api/v1/investigations/{id}/recommendations` | Draft recommendation | Access | recommendation:create |

### 14.6 Recommendations
| Method | Path | Purpose | Auth | Permission |
|--------|------|---------|------|------------|
| PATCH | `/api/v1/recommendations/{id}/review` | Approve/reject | Access | recommendation:approve |

### 14.7 Work Orders
| Method | Path | Purpose | Auth | Permission |
|--------|------|---------|------|------------|
| GET | `/api/v1/work-orders` | List | Access | work_order:read |
| POST | `/api/v1/work-orders` | Create | Access | work_order:create |
| GET | `/api/v1/work-orders/{id}` | Detail (with transitions, evidence, verifications) | Access | work_order:read |
| PATCH | `/api/v1/work-orders/{id}` | Status transition | Access | work_order:complete / verify |
| POST | `/api/v1/work-orders/{id}/evidence` | Upload completion evidence | Access | work_order:complete |
| POST | `/api/v1/work-orders/{id}/completion` | Submit completion | Access | work_order:complete |
| POST | `/api/v1/work-orders/{id}/verifications` | Verify completion | Access | work_order:verify |

### 14.8 Registry (Admin)
| Method | Path | Purpose | Auth | Permission |
|--------|------|---------|------|------------|
| GET/POST | `/api/v1/departments` | List/create | Access | registry:read/manage |
| GET/POST | `/api/v1/contractors` | List/create | Access | registry:read/manage |
| GET/POST | `/api/v1/assets` | List/create | Access | registry:read/manage |
| GET/POST | `/api/v1/contracts` | List/create | Access | registry:read/manage |

### 14.9 Hotspots & Accidents
| Method | Path | Purpose | Auth | Permission |
|--------|------|---------|------|------------|
| GET | `/api/v1/hotspots` | List analyses | Access | analytics:read |
| POST | `/api/v1/hotspots/analyze` | Run DBSCAN | Access | hotspot:analyze |
| GET | `/api/v1/hotspots/geojson` | GeoJSON for map | Access | analytics:read |
| GET | `/api/v1/accident-records` | List historical | Access | analytics:read |
| POST | `/api/v1/accident-records/import` | CSV import | Access | registry:manage |

### 14.10 Audit & Realtime
| Method | Path | Purpose | Auth | Permission |
|--------|------|---------|------|------------|
| GET | `/api/v1/audit-logs` | List audit entries | Access | audit:read |
| GET | `/api/v1/realtime/ticket` | WebSocket ticket | Access | — |
| WS | `/api/v1/realtime/ws?ticket=...` | Event stream | Ticket | — |
---

## SECTION 15 — Real-time and Background Processing

### 15.1 Celery Architecture
- **Broker:** Redis (`redis://redis:6379/0`).
- **Task:** `process_ai_job` in `ai_engine/workers/celery_app.py`.
- **Concurrency:** Prefork pool; `worker_prefetch_multiplier=1`.
- **Result backend:** Redis (optional, not used for job status — DB is source of truth).

### 15.2 Polling Worker (Brokerless Fallback)
- **File:** `ai_engine/workers/polling_worker.py`.
- **Loop:** `claim_ai_job(worker_id, lease_seconds=300, max_attempts=3)` → `process_job` → repeat.
- **Claim function:** `SECURITY DEFINER` SQL function — only sanctioned cross-tenant read.
- **Lease:** `jobs.lease_expires_at`; expired leases re-claimed by other workers.

### 15.3 Job Status Transitions
```
queued → claimed (lease set) → processing (stage: decoding/detecting/tracking/rules/evidence)
    → succeeded (result_summary populated)
    → failed (validation_error set)
```
- **Retry:** `attempts` counter; `max_attempts=3`; exponential backoff in Celery; polling worker re-claims on lease expiry.
- **Idempotency:** `jobs.idempotency_key` (video_id + force_reprocess flag) prevents duplicate processing.

### 15.4 Progress Reporting
- **Job.stage:** `decoding` → `detecting` → `tracking` → `evaluating_rules` → `generating_evidence` → `finalizing`.
- **Job.progress:** 0–100% updated per stage.
- **Frontend:** Polls `/api/v1/jobs` via `useApi` (refetch interval not configured; manual refresh button).

### 15.5 WebSocket Events
| Event Type | Payload | Trigger |
|------------|---------|---------|
| `incident.reviewed` | `{incident_id, review_status, reviewed_by}` | `PATCH /incidents/{id}/review` |
| `job.status_changed` | `{job_id, status, stage, progress}` | Pipeline stage updates |
| `work_order.transitioned` | `{work_order_id, from_status, to_status}` | `PATCH /work-orders/{id}` |

### 15.6 Organization Isolation in Realtime
- **Ticket:** `GET /api/v1/realtime/ticket` → JWT with `organization_id` claim, 60s expiry, single-use.
- **Hub:** In-process `EventHub` (default) + optional Redis pub/sub bridge.
- **Subscription:** On connect, hub adds connection to `organization_id` room.
- **Publish:** `publish_event(org_id, event)` → delivers to all connections in that room.

---

## SECTION 16 — Security Architecture

### 16.1 Authentication
- **Password hash:** Argon2id (via `passlib`).
- **Access JWT:** RS256, 15 min expiry, claims: `sub`, `email`, `roles[]`, `organization_id`, `session_id`.
- **Refresh token:** Opaque random string; SHA-256 hash stored in `refresh_sessions`; rotated on use; revocable.
- **Cookies:** `HttpOnly`, `Secure` (in production), `SameSite=Lax`, path `/`.

### 16.2 CSRF Protection
- **Double-submit:** `GET /api/v1/auth/csrf` sets `csrf_token` cookie; all unsafe methods require `x-csrf-token` header matching cookie.
- **Exempt:** `login`, `refresh`, `logout`, `health`, `csrf` bootstrap.

### 16.3 RBAC
- **Permission catalogue:** 20+ permissions in `core/permissions.py`.
- **Role mapping:** `ROLE_PERMISSIONS` dict.
- **Enforcement:** `require_permission(perm)` FastAPI dependency checks JWT `roles` claim.
- **RLS:** Every query filtered by `app.current_organization_id` GUC.

### 16.4 PostgreSQL RLS
- **App role:** `roadguard_app` (`NOSUPERUSER`, `NOBYPASSRLS`).
- **Policies:** 23 tables with `USING (organization_id = current_setting('app.current_organization_id')::uuid)`.
- **Force:** `ALTER TABLE ... FORCE ROW LEVEL SECURITY` on all tenant tables.
- **Cross-tenant read:** Returns 404 (not 403) — verified in security tests.

### 16.5 Composite Foreign Keys
- All tenant tables: `(id, organization_id)` PK.
- FKs reference both columns — prevents cross-tenant references at schema level.

### 16.6 Storage Security
- **Private bucket:** `roadguard-private` (MinIO) — no public access.
- **Signed URLs:** Short-lived (default 15 min); GET for download, PUT for upload.
- **Tenant scope check:** Download endpoint verifies `evidence.organization_id == current_org` before signing.

### 16.7 RTSP Credential Protection
- **Not stored in DB:** RTSP URLs/credentials kept in external secret manager (not implemented).
- **Adapter:** `RTSPAdapter` in `ai_engine/video/rtsp_adapter.py` — reports `BLOCKED` until allowlisted source configured.
- **Simulated live:** Explicitly labelled; no real connection attempted.

### 16.8 Audit Logging
- **Append-only:** `REVOKE UPDATE, DELETE ON audit_logs FROM roadguard_app`.
- **Trigger:** `audit_log_immutability_trigger` rejects non-owner writes.
- **Captured:** All consequential actions (create/update/delete/review/approve/verify/transition).

### 16.9 Rate Limiting
- **Login:** `SlidingWindowLimiter` (in-process, 5 req/min per IP).
- **Limitation:** Single-process; multi-replica needs Redis-backed limiter.

### 16.10 Security Headers (Next.js proxy)
```
x-content-type-options: nosniff
x-frame-options: DENY
referrer-policy: no-referrer
```
---

## SECTION 17 — Infrastructure and Deployment

### 17.1 Docker Compose Services
```yaml
# docker-compose.yml
services:
  postgres:
    image: postgis/postgis:16-3.4
    environment: POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
    volumes: postgres_data, ./infrastructure/postgres/init.sh
    healthcheck: pg_isready

  redis:
    image: redis:7-alpine
    healthcheck: redis-cli ping

  minio:
    image: cgr.dev/chainguard/minio:latest  # Chainguard build (Docker Hub minio removed)
    command: server /data --console-address ":9001"
    environment: MINIO_ROOT_USER, MINIO_ROOT_PASSWORD
    volumes: minio_data
    healthcheck: mc ready local

  minio-init:
    image: amazon/aws-cli:latest
    depends_on: [minio]
    entrypoint: mc alias set local http://minio:9000 ... && mc mb --ignore-existing local/roadguard-private

  api:
    build: {context: ., dockerfile: infrastructure/docker/api.Dockerfile}
    environment: DATABASE_URL, REDIS_URL, S3_*, JWT_*, DETECTOR_BACKEND, etc.
    depends_on: [postgres, redis, minio]
    ports: ["8000:8000"]
    healthcheck: curl /health/live

  worker:
    build: {context: ., dockerfile: infrastructure/docker/worker.Dockerfile}
    environment: Same as api + CELERY_BROKER_URL
    depends_on: [postgres, redis, minio, api]
    command: python -m ai_engine.workers.polling_worker --loop  # or celery worker
    healthcheck: python -c "import redis; redis.Redis(...).ping()"

  web:
    build: {context: ., dockerfile: infrastructure/docker/web.Dockerfile, args: [API_INTERNAL_URL, NEXT_PUBLIC_WS_URL, NEXT_PUBLIC_MAP_TILE_URL]}
    environment: API_INTERNAL_URL
    depends_on: [api]
    ports: ["3000:3000"]
    healthcheck: curl /health
```

### 17.2 Networks & Volumes
- **Network:** `roadguard-net` (all services).
- **Volumes:** `postgres_data`, `minio_data`.

### 17.3 Environment Variables (Names Only)
| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | PostgreSQL connection (asyncpg) |
| `REDIS_URL` | Redis connection |
| `S3_ENDPOINT_URL` | Internal MinIO endpoint (e.g., `http://minio:9000`) |
| `S3_PUBLIC_ENDPOINT_URL` | Browser-reachable endpoint (e.g., `http://localhost:9000`) |
| `S3_ACCESS_KEY`, `S3_SECRET_KEY` | MinIO credentials |
| `S3_BUCKET` | `roadguard-private` |
| `JWT_PRIVATE_KEY`, `JWT_PUBLIC_KEY` | RS256 keys (PEM) |
| `JWT_ACCESS_TTL_SECONDS` | 900 |
| `REFRESH_TTL_DAYS` | 30 |
| `CSRF_SECRET` | CSRF token signing key |
| `DETECTOR_BACKEND` | `synthetic_scene` or `yolo` |
| `YOLO_WEIGHTS_PATH` | Path to .pt file (if yolo) |
| `MAX_UPLOAD_BYTES` | 209715200 |
| `MAX_VIDEO_DURATION_SECONDS` | 600 |
| `NEXT_PUBLIC_WS_URL` | WebSocket public URL (e.g., `ws://localhost:8000`) |
| `NEXT_PUBLIC_MAP_TILE_URL` | OSM tile template |

### 17.4 Setup Commands (Verified)
```bash
# 1. Start infra
docker compose up -d postgres redis minio minio-init

# 2. Run migrations (from apps/api)
cd apps/api && python -m alembic upgrade head

# 3. Seed demo data
cd ../.. && python scripts/seed_database.py

# 4. Generate demo clip
python scripts/generate_demo_clip.py

# 5. Start API + worker + web (or use full compose)
docker compose up -d api worker web

# 6. Run smoke test
python scripts/demo_smoke.py
# Or against container stack:
python scripts/demo_smoke.py --external-worker
```

### 17.5 Local Windows Deployment
- Docker Desktop with WSL2 backend.
- All compose commands work in PowerShell.
- `alembic.ini` uses relative paths — must run migrations from `apps/api` directory.

### 17.6 Restart & Recovery
- **API/Worker/Web:** Stateless; restart anytime.
- **PostgreSQL:** Data in `postgres_data` volume; `pg_dump` for backup.
- **MinIO:** Data in `minio_data` volume; bucket contents persist.
- **Redis:** Ephemeral (Celery broker only); no persistence needed.

---

## SECTION 18 — Testing and Quality Assurance

### 18.1 Test Suite
| Type | Location | Count | Status |
|------|----------|-------|--------|
| Unit (API) | `apps/api/tests/unit/` | 38 | PASS |
| Integration (API) | `apps/api/tests/integration/` | 23 | PASS |
| Frontend TypeScript | `apps/web/` | — | PASS (`tsc --noEmit`) |
| Frontend Build | `apps/web/` | — | PASS (`next build`) |
| Lint (Ruff) | `apps/api`, `ai-engine`, `scripts`, `tests` | — | PASS |

### 18.2 Key Integration Tests
- `test_video_pipeline.py` — Full upload → job → detection → incident.
- `test_api_security.py` — RBAC denials, cross-tenant 404s, CSRF rejection.
- `test_endpoint_coverage.py` — Walks dependency chain, diffs against OpenAPI (82 ops, 69 paths).
- `test_tenant_isolation.py` — RLS, composite FKs, audit immutability.

### 18.3 Test Execution Results (Latest)
```bash
$ python -m pytest
# 61 passed, 3 deprecation warnings (Starlette 422/413 constants)

$ npx tsc --noEmit
# no errors

$ npx next build
# success, 24 routes emitted
```

### 18.4 Not Implemented / Blocked
- **Playwright UI tests:** Tooling not installed.
- **axe accessibility audit:** Tooling not installed.
- **Load testing:** No generator; sampled read latency (median 5ms).
- **Container vulnerability scan:** Not executed.
- **YOLO accuracy benchmark:** Weights not installed.
- **RTSP integration test:** No authorised feed.
---

## SECTION 19 — Complete End-to-End Workflow

### 19.1 Step-by-Step (Executed in `scripts/demo_smoke.py`)

| Step | Action | API Calls | Database Changes | Evidence |
|------|--------|-----------|------------------|----------|
| 1 | Sign in as ops@demo.roadguard.ai | `POST /auth/login` | `refresh_sessions` insert | Cookies set |
| 2 | Upload demo clip | `POST /videos/upload-url` → PUT MinIO → `POST /videos/{id}/complete-upload` → `POST /videos/{id}/process` | `videos`, `jobs` rows | Signed URL used |
| 3 | Worker processes job | (background) | `jobs` status → succeeded, `incidents` insert (1 near_miss_candidate), `evidence` inserts (annotated frame + clip) | `job_succeeded events=1 detections=177` |
| 4 | Review incident | `GET /incidents`, `GET /incidents/{id}/evidence`, `PATCH /incidents/{id}/review` (confirm) | `incidents.review_status=confirmed`, `audit_logs` insert | Review decision recorded |
| 5 | Open investigation | `POST /investigations` | `investigations`, `investigation_hypotheses` | `INV-2026-0024` |
| 6 | Run analysis | `POST /investigations/{id}/analyze` | `investigations.analysis_source=deterministic`, hypotheses updated | Deterministic draft |
| 7 | Draft recommendation | `POST /investigations/{id}/recommendations` | `recommendations` (draft) | — |
| 8 | Approve recommendation (different user) | `PATCH /recommendations/{id}/review` (approve) | `recommendations.status=approved`, `audit_logs` | Self-approval rejected |
| 9 | Create work order | `POST /work-orders` | `work_orders` (pending) | — |
| 10 | Department accepts → completes → uploads evidence | `PATCH /work-orders/{id}` (assigned→in_progress→completed_pending_verification), `POST /work-orders/{id}/evidence`, `POST /work-orders/{id}/completion` | `work_orders`, `work_order_evidence`, `work_order_history`, `audit_logs` | Completion evidence uploaded |
| 11 | Independent verification (different user) | `POST /work-orders/{id}/verifications` (accept) | `work_order_verifications`, `work_orders.status=verified`, `audit_logs` | Separation of duties enforced |
| 12 | Audit trail review | `GET /audit-logs` | — | 100 audit entries |

### 19.2 Files Involved
- **Frontend:** All Command Center + Admin Portal pages.
- **Backend:** All 13 routers, 10 services, pipeline, detector, tracker, rules, evidence.
- **Database:** All 25 tables touched.
- **Storage:** MinIO (video, annotated frame, event clip, completion photo).
- **Worker:** Polling worker or Celery task.
---

## SECTION 20 — Known Limitations and Future Scope

### 20.1 Verified Capabilities
- Complete vertical slice on synthetic data with honest labelling.
- Tenant isolation enforced at DB + API layers.
- Separation of duties in recommendations, work orders, verifications.
- Append-only audit log at database level.
- Private storage with signed URLs.
- Real-time WebSocket with ticket auth.

### 20.2 Simulated Capabilities
- **AI Detection:** Synthetic scene detector only (colour markers on generated clip).
- **Live Monitoring:** Simulated replay explicitly labelled; no real RTSP.
- **Hotspot Rates:** DBSCAN clusters only; no exposure normalization.
- **LLM Analysis:** Adapter exists but `LLM_PROVIDER=none`; deterministic path only.

### 20.3 Partially Implemented Features
- **YOLO Adapter:** Code complete, import-guarded; blocked by missing `torch`/`ultralytics` + weights.
- **ByteTrack Adapter:** Code complete; optional dependency not installed.
- **Redis Pub/Sub Bridge:** Code exists for WebSocket fan-out; only single-process verified.

### 20.4 Known Technical Limitations
| Limitation | Impact |
|------------|--------|
| In-process rate limiter | Resets on restart; no cross-replica coordination |
| Single WebSocket hub process | No horizontal scale without Redis bridge |
| No retention/deletion policy | Real footage storage needs legal hold + purge workflow |
| No backup/restore rehearsal | `pg_dump` + bucket sync not tested |
| No container vulnerability scan | Unknown CVE exposure in images |
| No automated UI/a11y tests | Manual verification only |

### 20.5 Unavailable Integrations
- Real RTSP camera (needs authorization + credentials).
- Supabase managed PostgreSQL (needs project DSN).
- External datasets (AI City Track 4, RDD2022, BDD100K — all blocked).
- Email/SMS/payment/notification providers.

### 20.6 Required External Credentials
- `SUPABASE_DB_URL` + `SUPABASE_POOLER_URL` (for managed DB).
- RTSP camera URL + credentials (for live feed).
- YOLO weights file (for real detection).
- LLM API key (for LLM-assisted analysis).
- Licensed map tile server URL (for production).

### 20.7 Potential Improvements
- Exposure-normalised hotspot rates (needs traffic volume data).
- Multi-camera tracking / re-identification.
- Automated retention + legal hold workflow.
- Kubernetes deployment manifests.
- Playwright + axe test suite.
- Dependency/container scanning in CI.

### 20.8 Future Production Requirements
1. Licensed detector benchmarked on Indian CCTV data.
2. Authorised RTSP feed with credential management.
3. CSP/HSTS/secure cookie flags configured.
4. Retention/deletion policy implemented and rehearsed.
5. Backup/restore tested.
6. Vulnerability scan baseline established.
7. Accessibility audit (WCAG 2.1 AA).
---

## SECTION 21 — Developer Maintenance Guide

### 21.1 Folder Structure
```
Nagar-Setu/
├── apps/
│   ├── api/              # FastAPI backend
│   │   ├── app/          # Application code
│   │   ├── alembic/      # Migrations
│   │   ├── tests/        # Pytest suite
│   │   └── requirements.txt
│   └── web/              # Next.js frontend
│       ├── app/          # App Router pages
│       ├── components/   # React components
│       ├── lib/          # Hooks, utilities, API client
│       └── package.json
├── ai-engine/            # Computer vision pipeline
│   ├── ai_engine/
│   │   ├── detection/    # Detector adapters
│   │   ├── tracking/     # Trackers
│   │   ├── events/       # Rule evaluators
│   │   ├── video/        # Decoder, evidence, RTSP
│   │   ├── pipeline.py   # Job orchestration
│   │   └── workers/      # Celery + polling worker
│   └── requirements.txt
├── scripts/              # Seed, demo clip, smoke test, dataset tools
├── infrastructure/       # Dockerfiles, postgres init
├── docs/                 # All documentation
├── docker-compose.yml
├── docker-compose.supabase.yml
└── README.md
```

### 21.2 Dependency Installation
```bash
# Backend
cd apps/api && pip install -r requirements.txt

# AI Engine
cd ai-engine && pip install -r requirements.txt

# Frontend
cd apps/web && npm ci
```

### 21.3 Environment Configuration
- Copy `.env.example` → `.env` and fill values.
- Key variables: `DATABASE_URL`, `REDIS_URL`, `S3_*`, `JWT_*`, `DETECTOR_BACKEND`.

### 21.4 Database Commands
```bash
cd apps/api
# Upgrade to head
python -m alembic upgrade head
# Create new migration
python -m alembic revision --autogenerate -m "description"
# Current revision
python -m alembic current
```

### 21.5 Docker Commands
```bash
# Build all images
docker compose build

# Start full stack
docker compose up -d

# View logs
docker compose logs -f api
docker compose logs -f worker
docker compose logs -f web

# Stop all
docker compose down

# Stop + remove volumes (clean slate)
docker compose down -v
```

### 21.6 Frontend Development
```bash
cd apps/web
npm run dev        # Development server (Turbopack)
npm run build      # Production build
npm run typecheck  # TypeScript check
npm run lint       # ESLint
```

### 21.7 Backend Development
```bash
cd apps/api
# Run API server (dev)
uvicorn app.main:app --reload --port 8000

# Run worker (polling)
python -m ai_engine.workers.polling_worker --loop

# Run worker (Celery)
celery -A ai_engine.workers.celery_app worker --loglevel=info
```

### 21.8 AI Worker Execution
```bash
# From repo root
python -m ai_engine.workers.polling_worker --once  # Single job
python -m ai_engine.workers.polling_worker --loop  # Continuous
```

### 21.9 Test Execution
```bash
# Backend tests
cd apps/api && python -m pytest -v

# Frontend typecheck + build
cd apps/web && npx tsc --noEmit && npx next build

# Lint
cd apps/api && python -m ruff check .
cd apps/web && npm run lint
```

### 21.10 Dataset Management
```bash
# Validate incoming clips
python scripts/prepare_dataset.py --input datasets/incoming

# Upload validated clips (requires running API + worker)
DEMO_SEED_PASSWORD=... python scripts/prepare_dataset.py \
  --input datasets/incoming --upload \
  --api-url http://localhost:8000 --email ops@demo.roadguard.ai --wait-seconds 300
```

### 21.11 Debugging
- **API logs:** `docker compose logs -f api` or uvicorn console.
- **Worker logs:** `docker compose logs -f worker` or polling worker console.
- **Database:** `docker compose exec postgres psql -U roadguard -d roadguard`
- **MinIO console:** `http://localhost:9001` (credentials from `.env`).
- **Frontend console:** Browser DevTools (Network, Console, React DevTools).

### 21.12 Common Errors & Troubleshooting
| Error | Cause | Fix |
|-------|-------|-----|
| `alembic: Target database not up to date` | Migration not run | `cd apps/api && python -m alembic upgrade head` |
| `S3 presigned URL fails` | `S3_PUBLIC_ENDPOINT_URL` wrong | Set to browser-reachable MinIO (e.g., `http://localhost:9000`) |
| `WebSocket connection fails` | `NEXT_PUBLIC_WS_URL` mismatch | Match API host + `/api/v1/realtime/ws` |
| `Job stuck in queued` | Worker not running | Start polling worker or Celery worker |
| `RLS policy violation` | `app.current_organization_id` not set | Check `tenant_session` middleware |
| `CSRF token mismatch` | Cookie/header missing | Ensure `api.ts` interceptor adds header |
| `next dev` filesystem notice | `.next` written by production build | Restart dev server |
---

## SECTION 22 — Glossary

| Term | Meaning in This Codebase |
|------|-------------------------|
| **Candidate event** | AI-produced observation awaiting human review (`review_status=pending`). Not an accident. |
| **Incident** | Stored record of an event (AI or manual). `source_kind` distinguishes them. |
| **Confirmed observation** | Incident a human reviewer accepted. Still not a legal finding. |
| **Historical accident record** | Imported CSV row with `source_name`, `source_reference`, `verification_status`. Never merged into AI counts. |
| **Evidence artefact** | Private stored file (annotated frame, event clip, completion photo) with checksum, type, timestamp. |
| **Hotspot / cluster** | Concentration of located records from DBSCAN within radius. Not an exposure-adjusted risk rate. |
| **Investigation / case** | Record holding observed facts, hypotheses, missing information, evidence references, human decisions. |
| **Hypothesis** | Possible root cause with confidence *label* and cited supporting records. Never a conclusion. |
| **Recommendation** | Proposed corrective action requiring independent approval before work order exists. |
| **Work order** | Actionable instruction to a department with validated state machine and completion evidence. |
| **Verification** | Different user's decision that completion evidence satisfies the work order. |
| **Separation of duties** | Recommender ≠ approver; completer ≠ verifier. Enforced in code. |
| **Simulated live** | Replay of recorded footage explicitly labelled SIMULATED LIVE; never a real camera feed. |
| **DEMO** | Synthetic seeded/generated data, labelled in UI and stored with `is_demo=true`. |
| **Image-plane measurement** | Quantity in pixels or normalized pixels. Never metres, m/s, or seconds-to-collision. |
| **Ticket (realtime)** | Single-use 60-second JWT authorising one WebSocket connection for one organization. |
| **Claim / lease** | Worker's time-boxed ownership of a job row with attempts and retry limits. |
---

## SECTION 23 — Final Implementation Summary

### 23.1 What the Application Currently Does
ROADGUARD AI is a **complete, demonstrable vertical slice** of a government road-safety intelligence platform that:
1. Accepts CCTV footage uploads to private object storage via signed URLs.
2. Queues background AI jobs (Celery or polling worker) that run detection/tracking on a **synthetic scene detector** (OpenCV colour-marker segmentation on a generated clip).
3. Produces **candidate events** (near-miss, collision candidate, pedestrian conflict, rapid motion, wrong-way, signal violation) with annotated frames and event clips as evidence.
4. Routes candidates through a **human review queue** (confirm/reject/needs-more-info) with full audit trail.
5. Opens **investigations** that deterministically match event location → nearest asset → owning department → active maintenance contracts → contractors.
6. Drafts **root-cause hypotheses** (deterministic rules; LLM adapter not exercised).
7. Creates **recommendations** requiring **independent approval** (self-approval rejected).
8. Converts approved recommendations to **work orders** with a validated state machine.
9. Tracks **completion evidence upload** and **independent verification** (separation of duties enforced).
10. Visualizes **hotspot clusters** (DBSCAN on PostGIS geography) combining confirmed AI observations and historical accident records — explicitly labelled as clusters, not risk rates.
11. Maintains **administrative registries** for departments, contractors, assets, contracts.
12. Provides **real-time WebSocket updates** (ticket-authenticated) for incident reviews and job status changes.
13. Enforces **multi-tenant isolation** at four layers (JWT org context, composite FKs, transaction GUC, RLS policies).
14. Records every consequential action in an **append-only audit log** (DB-level revoke + trigger).

### 23.2 Module Interaction Summary
```
Browser (Next.js)
    │  Cookies + CSRF header
    ▼
Next.js Proxy (/api/* → FastAPI)
    │
    ├─→ FastAPI (auth, RBAC, RLS context)
    │       │
    │       ├─→ PostgreSQL + PostGIS (tenant-isolated)
    │       │
    │       ├─→ MinIO/S3 (private storage, signed URLs)
    │       │
    │       └─→ Redis (Celery broker + realtime pub/sub)
    │
    └─→ WebSocket (ticket auth) → EventHub → Browser

Background Worker (Celery or Polling)
    │
    ├─→ Claims job (SECURITY DEFINER claim_ai_job)
    │
    ├─→ Downloads video from MinIO
    │
    ├─→ Runs pipeline:
    │     Decoder → Detector (synthetic_scene) → Tracker (IoU) → 6 Rules → Evidence
    │
    ├─→ Writes incidents + evidence to PostgreSQL + MinIO
    │
    └─→ Publishes realtime events
```

### 23.3 What Makes the Product Distinctive
1. **Honest AI labelling** — "candidate," "not confirmed," "image-plane only" on every artefact.
2. **Deterministic responsibility chain** — asset → department → contract → contractor, all date-aware.
3. **Separation of duties in code** — not just policy; server rejects self-approval and self-verification.
4. **Append-only audit at DB level** — not application convention.
5. **Private storage by default** — no public URLs ever generated.
6. **No video in API** — uploads direct to object storage; API only creates job rows.

### 23.4 Current Verification Status
| Area | Status | Evidence |
|------|--------|----------|
| Authentication & RBAC | VERIFIED | 61 tests pass; auditor/engineer denials 403 |
| Multi-tenant isolation | VERIFIED | 23/23 RLS policies; zero cross-org rows |
| Video upload & processing | VERIFIED | Smoke test: upload → job → 1 candidate → evidence |
| AI detection (synthetic) | VERIFIED | Deterministic output on demo clip |
| Incident review | VERIFIED | 25 confirmed rows in demo |
| Investigation & responsibility | VERIFIED | `INV-2026-0024` with matched contracts |
| Recommendations & approval | VERIFIED | Self-approval blocked; independent approval recorded |
| Work orders & verification | VERIFIED | Full lifecycle + separation of duties |
| Hotspot analysis | VERIFIED | DBSCAN clusters on map + GeoJSON |
| Audit trail | VERIFIED | 100 entries in smoke test; DB immutability test |
| WebSocket realtime | PARTIAL | Ticket auth + connect verified; broadcast not asserted E2E |
| Real YOLO detection | BLOCKED | Weights not installed |
| Real RTSP | BLOCKED | No authorised feed |
| Road-damage detection | NOT IMPLEMENTED | No model |
| Automated UI/a11y/load tests | NOT IMPLEMENTED | Tooling not installed |

### 23.5 Known Limitations (Summary)
- **No real-world detection accuracy** — synthetic detector only; no labelled Indian CCTV dataset acquired.
- **No live RTSP** — simulated replay only.
- **No exposure-normalised hotspot rates** — traffic volume data not ingested.
- **No retention/deletion policy** — required for real footage.
- **Single-process rate limiter** — needs Redis for multi-replica.
- **No automated accessibility/load testing** — manual verification only.

### 23.6 Current Release Readiness
**Ready for:** Hackathon demonstration on synthetic data with limitations stated out loud.
**Not ready for:** Pilot on real footage until:
1. Authorised RTSP feed exists.
2. Licensed detector installed and benchmarked on labelled data.
3. CSP/HSTS/secure cookie flags configured.
4. UI/a11y test gap closed.
5. Retention/deletion policy implemented.
6. Vulnerability scan baseline established.

The single most impactful improvement for demo credibility: **AI City Track 4 labels driving a real precision/recall number** — the tooling to produce it is finished and waiting for the archive.

---

*Document generated from actual source code inspection. Every technical claim cites repository file paths and function/class/endpoint names. Behaviours not verified are explicitly marked NOT VERIFIED, NOT IMPLEMENTED, or BLOCKED.*
## SECTION 2 — Complete Feature Inventory