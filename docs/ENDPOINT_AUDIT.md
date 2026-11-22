# API endpoint audit

**Surface:** 82 operations across 69 documented paths, plus the
ticket-authenticated WebSocket which OpenAPI does not describe.

Every operation in this table is executed by
`tests/integration/test_endpoint_coverage.py` against a running API and database.
The suite walks the real dependency order (registry -> camera -> signed upload -> job ->
incident -> accident import -> hotspots -> investigation -> recommendation -> work order ->
completion evidence -> independent verification -> audit -> realtime) and then diffs the
operations it called against the live OpenAPI document. A documented operation that is never
called fails the test, so a new route cannot ship unexercised.

A second test replays every operation without a session and fails on any 2xx outside the five
intentional pre-auth endpoints: the health probes, the static permission catalogue, the CSRF
bootstrap cookie and idempotent logout. The three `storage/*` routes carry a short-lived signed
object token instead of a session; they reject missing/invalid tokens.

| # | Method | Path | Access |
|---|---|---|---|
| 1 | `GET` | `/api/v1/accident-records` | session |
| 2 | `GET` | `/api/v1/assets` | session |
| 3 | `GET` | `/api/v1/assets/nearby` | session |
| 4 | `GET` | `/api/v1/assets/{asset_id}` | session |
| 5 | `GET` | `/api/v1/assets/{asset_id}/responsibility` | session |
| 6 | `GET` | `/api/v1/audit-logs` | session |
| 7 | `GET` | `/api/v1/auth/csrf` | public |
| 8 | `GET` | `/api/v1/auth/me` | session |
| 9 | `GET` | `/api/v1/cameras` | session |
| 10 | `GET` | `/api/v1/cameras/{camera_id}` | session |
| 11 | `GET` | `/api/v1/cameras/{camera_id}/health` | session |
| 12 | `GET` | `/api/v1/contractors` | session |
| 13 | `GET` | `/api/v1/contractors/{contractor_id}` | session |
| 14 | `GET` | `/api/v1/contracts` | session |
| 15 | `GET` | `/api/v1/contracts/{contract_id}` | session |
| 16 | `GET` | `/api/v1/departments` | session |
| 17 | `GET` | `/api/v1/departments/{department_id}` | session |
| 18 | `GET` | `/api/v1/evidence/{evidence_id}` | session |
| 19 | `GET` | `/api/v1/evidence/{evidence_id}/url` | session |
| 20 | `GET` | `/api/v1/health/live` | public |
| 21 | `GET` | `/api/v1/health/ready` | public |
| 22 | `GET` | `/api/v1/hotspots` | session |
| 23 | `GET` | `/api/v1/hotspots/geojson` | session |
| 24 | `GET` | `/api/v1/hotspots/{hotspot_id}` | session |
| 25 | `GET` | `/api/v1/incidents` | session |
| 26 | `GET` | `/api/v1/incidents/analytics` | session |
| 27 | `GET` | `/api/v1/incidents/{incident_id}` | session |
| 28 | `GET` | `/api/v1/incidents/{incident_id}/evidence` | session |
| 29 | `GET` | `/api/v1/investigations` | session |
| 30 | `GET` | `/api/v1/investigations/{investigation_id}` | session |
| 31 | `GET` | `/api/v1/investigations/{investigation_id}/recommendations` | session |
| 32 | `GET` | `/api/v1/jobs` | session |
| 33 | `GET` | `/api/v1/jobs/{job_id}` | session |
| 34 | `GET` | `/api/v1/meta/bootstrap` | session |
| 35 | `GET` | `/api/v1/meta/permissions` | public |
| 36 | `GET` | `/api/v1/storage/download/{token}` | signed token |
| 37 | `GET` | `/api/v1/storage/local-object-exists/{token}` | signed token |
| 38 | `GET` | `/api/v1/users` | session |
| 39 | `GET` | `/api/v1/videos` | session |
| 40 | `GET` | `/api/v1/videos/{video_id}` | session |
| 41 | `GET` | `/api/v1/videos/{video_id}/playback-url` | session |
| 42 | `GET` | `/api/v1/work-orders` | session |
| 43 | `GET` | `/api/v1/work-orders/{work_order_id}` | session |
| 44 | `PATCH` | `/api/v1/assets/{asset_id}` | session |
| 45 | `PATCH` | `/api/v1/cameras/{camera_id}` | session |
| 46 | `PATCH` | `/api/v1/incidents/{incident_id}/review` | session |
| 47 | `PATCH` | `/api/v1/investigations/{investigation_id}` | session |
| 48 | `PATCH` | `/api/v1/recommendations/{recommendation_id}/review` | session |
| 49 | `PATCH` | `/api/v1/users/{user_id}` | session |
| 50 | `PATCH` | `/api/v1/work-orders/{work_order_id}` | session |
| 51 | `POST` | `/api/v1/accident-records/import` | session |
| 52 | `POST` | `/api/v1/assets` | session |
| 53 | `POST` | `/api/v1/auth/change-password` | session |
| 54 | `POST` | `/api/v1/auth/login` | session |
| 55 | `POST` | `/api/v1/auth/logout` | public |
| 56 | `POST` | `/api/v1/auth/refresh` | session |
| 57 | `POST` | `/api/v1/cameras` | session |
| 58 | `POST` | `/api/v1/cameras/{camera_id}/disable` | session |
| 59 | `POST` | `/api/v1/cameras/{camera_id}/enable` | session |
| 60 | `POST` | `/api/v1/cameras/{camera_id}/live/rtsp` | session |
| 61 | `POST` | `/api/v1/cameras/{camera_id}/live/simulate` | session |
| 62 | `POST` | `/api/v1/cameras/{camera_id}/live/stop` | session |
| 63 | `POST` | `/api/v1/contractors` | session |
| 64 | `POST` | `/api/v1/contracts` | session |
| 65 | `POST` | `/api/v1/departments` | session |
| 66 | `POST` | `/api/v1/hotspots/analyze` | session |
| 67 | `POST` | `/api/v1/incidents/manual` | session |
| 68 | `POST` | `/api/v1/investigations` | session |
| 69 | `POST` | `/api/v1/investigations/{investigation_id}/analyze` | session |
| 70 | `POST` | `/api/v1/investigations/{investigation_id}/assign` | session |
| 71 | `POST` | `/api/v1/investigations/{investigation_id}/recommendations` | session |
| 72 | `POST` | `/api/v1/jobs/{job_id}/retry` | session |
| 73 | `POST` | `/api/v1/realtime/ticket` | session |
| 74 | `POST` | `/api/v1/users` | session |
| 75 | `POST` | `/api/v1/videos/upload-url` | session |
| 76 | `POST` | `/api/v1/videos/{video_id}/complete-upload` | session |
| 77 | `POST` | `/api/v1/videos/{video_id}/process` | session |
| 78 | `POST` | `/api/v1/work-orders` | session |
| 79 | `POST` | `/api/v1/work-orders/{work_order_id}/completion` | session |
| 80 | `POST` | `/api/v1/work-orders/{work_order_id}/evidence` | session |
| 81 | `POST` | `/api/v1/work-orders/{work_order_id}/verifications` | session |
| 82 | `PUT` | `/api/v1/storage/upload/{token}` | signed token |

---

Reproduce:

```bash
python -m pytest tests/integration/test_endpoint_coverage.py -v
```
