# API Specification

**Base path:** `/api/v1`  
**Version:** 1.0  
**Transport:** HTTPS REST; WebSocket for optional realtime hints  
**Status:** Contract baseline; FastAPI OpenAPI is the executable source after implementation.

## 1. API conventions

- JSON request/response bodies unless uploading directly to object storage.
- UUID identifiers.
- UTC ISO-8601 timestamps in persistence; return ISO-8601 with `Z` or explicit offset.
- Pagination: `limit` (default 25, max 100) and opaque `cursor` or `offset` consistently per endpoint family. Prefer cursor pagination for high-volume events.
- Filtering must be tenant-scoped before applying user filters.
- The server derives organization and role from the authenticated principal.
- Use `Idempotency-Key` for retryable create/submit operations where duplicate effects are possible.
- Never return password hashes, raw RTSP credentials, private storage keys that bypass authorization, or secret-manager values.

## 2. Standard success and error shapes

Success example:

```json
{
  "data": { "id": "uuid", "status": "queued" },
  "meta": { "request_id": "uuid" }
}
```

Error example:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The uploaded file is not a supported video type.",
    "details": [{ "field": "content_type", "reason": "unsupported" }]
  },
  "meta": { "request_id": "uuid" }
}
```

Use meaningful HTTP status codes: 400 malformed request, 401 unauthenticated, 403 forbidden, 404 not found or not visible in tenant, 409 state conflict, 413 too large, 415 unsupported media, 422 semantically invalid, 429 rate limited, 500 unexpected server failure, 503 dependency unavailable.

## 3. Authentication

| Method | Path | Purpose | Access |
|---|---|---|---|
| POST | `/auth/login` | Authenticate and create session | Public, rate-limited |
| POST | `/auth/refresh` | Rotate refresh token/session | Valid refresh cookie |
| POST | `/auth/logout` | Revoke session | Authenticated |
| GET | `/auth/me` | Current profile and effective permissions | Authenticated |
| POST | `/auth/change-password` | Change password | Authenticated |

Login response must not expose another user's data. Refresh tokens should be rotated/revoked securely and stored as hashes server-side if persisted. CSRF protection is required when cookie-based auth is used for state-changing requests.

## 4. Cameras

| Method | Path | Purpose | Access |
|---|---|---|---|
| GET | `/cameras` | Paginated camera list | Camera viewer |
| POST | `/cameras` | Register camera | Camera manager |
| GET | `/cameras/{camera_id}` | Camera detail | Camera viewer |
| PATCH | `/cameras/{camera_id}` | Update metadata | Camera manager |
| POST | `/cameras/{camera_id}/enable` | Enable configured source | Camera manager |
| POST | `/cameras/{camera_id}/disable` | Disable source | Camera manager |
| GET | `/cameras/{camera_id}/health` | Health/status | Camera viewer |

Create request example:

```json
{
  "camera_code": "DEMO-CAM-004",
  "name": "Demo Intersection North",
  "source_type": "upload_association",
  "location": { "latitude": 20.2961, "longitude": 85.8245 },
  "description": "Synthetic demonstration camera"
}
```

`source_type` may include `upload_association`, `rtsp` or `demo_replay`. Enabling RTSP requires server-side secret configuration and an authorized host allowlist; the client must not submit a raw URL as a way to connect to arbitrary hosts.

## 5. Videos and processing jobs

| Method | Path | Purpose | Access |
|---|---|---|---|
| POST | `/videos/upload-url` | Create private upload session | Video uploader |
| POST | `/videos/{video_id}/complete-upload` | Verify uploaded object and finalize | Video uploader |
| GET | `/videos` | List video metadata | Video viewer |
| GET | `/videos/{video_id}` | Video details | Video viewer |
| POST | `/videos/{video_id}/process` | Enqueue processing | Video processor |
| GET | `/jobs/{job_id}` | Job state/progress | Job viewer |
| POST | `/jobs/{job_id}/retry` | Retry eligible failed job | Job manager |
| GET | `/videos/{video_id}/playback-url` | Short-lived authorized playback URL | Evidence viewer |

Upload session request:

```json
{
  "filename": "demo_intersection.mp4",
  "content_type": "video/mp4",
  "file_size_bytes": 18400000,
  "camera_id": "uuid-or-null",
  "recorded_at": "2026-11-18T08:00:00Z",
  "source_type": "upload"
}
```

Upload response:

```json
{
  "data": {
    "video_id": "uuid",
    "upload_url": "short-lived-signed-url",
    "upload_method": "PUT",
    "expires_at": "2026-11-18T08:15:00Z"
  }
}
```

The signed URL is returned only to the authorized uploader and is never written to normal logs. The completion endpoint verifies object existence, size and checksum before enqueueing.

Job response:

```json
{
  "data": {
    "id": "uuid",
    "video_id": "uuid",
    "status": "running",
    "progress": 42,
    "stage": "tracking",
    "error_code": null
  }
}
```

Allowed job states: `queued`, `running`, `succeeded`, `failed`, `cancelled`.

## 6. Incidents and review

| Method | Path | Purpose | Access |
|---|---|---|---|
| GET | `/incidents` | Filter/paginate incidents | Incident viewer |
| GET | `/incidents/{incident_id}` | Incident detail | Incident viewer |
| GET | `/incidents/{incident_id}/evidence` | Evidence metadata | Evidence viewer |
| PATCH | `/incidents/{incident_id}/review` | Confirm/reject/request info | Incident reviewer |
| POST | `/incidents/manual` | Create manual observation | Incident contributor |
| GET | `/incidents/analytics` | Aggregated counts/trends | Analytics viewer |

Review request:

```json
{
  "decision": "confirmed",
  "notes": "Reviewed source clip and annotated frame; event is consistent with the configured near-miss rule."
}
```

Allowed decisions: `confirmed`, `rejected_false_positive`, `needs_more_information`. The API must record reviewer and timestamp. A decision does not make the event a verified historical accident.

## 7. Historical accidents and hotspots

| Method | Path | Purpose | Access |
|---|---|---|---|
| POST | `/accident-records/import` | Start CSV import | Data administrator |
| GET | `/accident-records` | List historical records | Analytics viewer |
| GET | `/hotspots` | Aggregate hotspot results | Analytics viewer |
| GET | `/hotspots/geojson` | Map-ready feature collection | Analytics viewer |
| POST | `/hotspots/analyze` | Start aggregate calculation | Analytics administrator |
| GET | `/hotspots/{hotspot_id}` | Hotspot details and methodology | Analytics viewer |

GeoJSON properties must include source categories, count window, calculation method and generated time. Do not combine accident and AI candidate counts without separate fields.

## 8. Departments, contractors, assets and contracts

| Method | Path | Purpose |
|---|---|---|
| GET/POST | `/departments` | List/create departments |
| GET/PATCH | `/departments/{id}` | Read/update department |
| GET/POST | `/contractors` | List/create contractors |
| GET/PATCH | `/contractors/{id}` | Read/update contractor |
| GET/POST | `/assets` | List/create assets |
| GET/PATCH | `/assets/{id}` | Read/update asset |
| GET | `/assets/{id}/responsibility` | Retrieve linked responsibility records |
| GET/POST | `/contracts` | List/create contracts |
| GET/PATCH | `/contracts/{id}` | Read/update contract |

All mutations require role and organization checks. Responsibility response should return matching department/contract record identifiers, effective dates, scope notes and source references. It must not return a legal conclusion.

## 9. Investigations and recommendations

| Method | Path | Purpose |
|---|---|---|
| GET/POST | `/investigations` | List/create investigations |
| GET | `/investigations/{id}` | Detail and linked records |
| PATCH | `/investigations/{id}` | Update permitted case fields |
| POST | `/investigations/{id}/analyze` | Generate draft root-cause analysis |
| POST | `/investigations/{id}/assign` | Assign department/user |
| POST | `/investigations/{id}/recommendations` | Save draft recommendation |
| PATCH | `/recommendations/{id}/review` | Approve/reject/edit recommendation |

Investigation analysis must be asynchronous if model latency is material. Store the prompt/template version and structured input snapshot, excluding unnecessary sensitive data. The model may only use supplied records; no unsupported external claims.

## 10. Work orders and verification

| Method | Path | Purpose |
|---|---|---|
| GET/POST | `/work-orders` | List/create work orders |
| GET | `/work-orders/{id}` | Work-order detail/history |
| PATCH | `/work-orders/{id}` | Update permitted fields/status |
| POST | `/work-orders/{id}/completion` | Submit completion evidence |
| POST | `/work-orders/{id}/verifications` | Accept/reject/request more evidence |

Suggested status lifecycle:

`draft -> pending -> assigned -> in_progress -> completed_pending_verification -> verified`

Alternative terminal states: `cancelled`, `rejected`, `reopened`.

Enforce allowed transitions in the backend. A department assignee cannot mark a work order `verified`. Verification is a separate action by a permitted reviewer.

## 11. Audit and administrative endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/audit-logs` | Filter audit trail; auditor/admin |
| GET/POST/PATCH | `/users` and `/users/{id}` | User administration |
| GET | `/health/live` | Process liveness |
| GET | `/health/ready` | Dependency readiness without secret leakage |

Do not provide ordinary API routes to edit or delete audit entries.

## 12. WebSocket contract

Path: `/api/v1/ws/command-center`.

Authenticate using the application's secure session/token mechanism. The backend derives tenant scope from the principal. Example message:

```json
{
  "event_id": "uuid",
  "event_type": "video.processing_progress",
  "schema_version": "1.0",
  "occurred_at": "2026-11-18T08:30:00Z",
  "data": {
    "job_id": "uuid",
    "video_id": "uuid",
    "status": "running",
    "progress": 42,
    "stage": "tracking"
  }
}
```

Supported event types: `camera.status_changed`, `video.processing_started`, `video.processing_progress`, `video.processing_completed`, `incident.detected`, `incident.reviewed`, `investigation.updated`, `work_order.updated`.

The UI must refresh from REST after reconnect and must tolerate duplicate/out-of-order notifications.

## 13. Authorization matrix

The exact policy is implemented as permission strings rather than frontend role-name checks. Example permissions:

- `camera:read`, `camera:manage`
- `video:upload`, `video:read`, `video:process`
- `incident:read`, `incident:review`, `incident:create`
- `asset:read`, `asset:manage`
- `contract:read`, `contract:manage`
- `investigation:read`, `investigation:manage`, `investigation:assign`
- `recommendation:review`
- `work_order:read`, `work_order:manage`, `work_order:complete`, `work_order:verify`
- `user:manage`, `audit:read`

Permission is checked together with organization scope and, where applicable, department/assignment scope.
