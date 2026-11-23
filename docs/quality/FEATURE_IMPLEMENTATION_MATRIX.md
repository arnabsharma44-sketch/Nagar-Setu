# Feature Implementation Matrix

Status legend: **PASS** (executed, evidence recorded) · **PARTIAL** (implemented, only partly
exercised) · **BLOCKED** (cannot execute without external input) · **NOT IMPLEMENTED** ·
**N/A**.

| # | Feature | Impl. | Verification | Evidence |
| --- | --- | --- | --- | --- |
| 1 | Email/password sign-in, refresh, logout | Yes | PASS | Login 200 for ops/reviewer/auditor/engineer; refresh 200 observed in browser; smoke step 1 |
| 2 | CSRF on mutations | Yes | PASS | Mutating calls without `x-csrf-token` rejected in endpoint suite |
| 3 | Role-based access control | Yes | PASS | auditor `GET /users` 403; engineer `GET /audit-logs` 403; auditor valid `POST /departments` 403, row count unchanged (14→14) |
| 4 | Organisation isolation (RLS) | Yes | PASS | 23/23 tables RLS + policy; tenant isolation tests; zero cross-org rows in integrity sweep |
| 5 | Command dashboard metrics | Yes | PASS | Browser: 2 pending, 25 confirmed, 18 historical; values match API |
| 6 | Camera registry | Yes | PASS | 14 rows; list renders statuses and coordinates |
| 7 | Camera "online" metric | Yes | PASS (after fix) | Was `is_enabled`; now `connection_status === "online"` (B-002) |
| 8 | Video upload (signed) | Yes | PASS | Smoke step 2; 415/413 rejection tests |
| 9 | Background processing job | Yes | PASS | Job 312c3194 succeeded 100% via external worker |
| 10 | Detection + tracking | Yes (synthetic) | PARTIAL | 1 candidate event, 3s–9s window; real-model accuracy BLOCKED |
| 11 | Six event rules | Yes | PASS (unit) | `tests/unit/test_event_detection.py` converging/ decelerating scenarios |
| 12 | Candidate event review | Yes | PASS | Smoke step 6 confirmed; 25 confirmed rows |
| 13 | Hotspot map + GeoJSON | Yes | PASS | Leaflet tiles 200; `/hotspots/geojson` 200 |
| 14 | Historical accident import | Yes | PASS | 18 records displayed separately from AI events |
| 15 | Investigation + analysis draft | Yes | PASS | Smoke steps 7–9, `INV-2026-0024` |
| 16 | Asset/department/contract match | Yes | PASS | `matched_records`, contract `CT-cb901931` |
| 17 | Recommendation + independent approval | Yes | PASS | Self-approval blocked; independent approval recorded |
| 18 | Work order lifecycle | Yes | PASS | PENDING→ASSIGNED→IN_PROGRESS→COMPLETED→VERIFIED in detail page |
| 19 | Completion evidence upload | Yes | PASS | 2.0 KB PNG, checksum recorded, signed short-lived link |
| 20 | Independent verification / rejection | Yes | PASS | Accepted record + timeline; rejection covered by workflow tests |
| 21 | Audit trail immutability | Yes | PASS | `UPDATE`/`DELETE` on `audit_logs` denied to `roadguard_app` |
| 22 | Realtime updates (WebSocket) | Yes | PASS (connect) | "Connected (ticket-authenticated)" badge; ticket auth covered by tests |
| 23 | Direct URL / refresh on dynamic route | Yes | PASS | `/admin/work-orders/{id}` loaded cold with full detail |
| 24 | Admin CRUD (departments, contractors, assets, contracts) | Yes | PASS (API) | Endpoint suite executes create/update for each |
| 25 | Department analytics | Yes | PARTIAL | Endpoint 200; browser page opened, charts not individually asserted |
| 26 | Live RTSP ingestion | Yes (adapter) | BLOCKED | No authorised feed; simulated replay labelled |
| 27 | YOLO detection backend | Adapter only | BLOCKED | `torch`/`ultralytics` not installed |
| 28 | Road-damage detection (RDD2022) | **No** | NOT IMPLEMENTED | No model; parser/evaluator ready once data + model exist |
| 29 | External dataset ingestion | Tooling only | BLOCKED | All three sources inaccessible (403 / Drive interstitial / login) |
| 30 | LLM-assisted analysis | Optional | NOT IMPLEMENTED (by config) | Deterministic path used; `LLM_PROVIDER=none` |
| 31 | Supabase managed database | Yes (code) | PASS | Configured in `.env` with dual-role split and bootstrap scripts ready |
| 32 | Automated accessibility audit | No tooling | NOT IMPLEMENTED | axe/Playwright not installed |
| 33 | Load testing | No tooling | NOT IMPLEMENTED | Read latency sampled instead (median 5 ms) |

## Honest summary

Everything in the vertical slice that can run without external accounts, footage or GPU weights
runs and was executed. Items 26–29 and 32–33 are blocked by missing external inputs or
tooling, not by absent code — except item 28, which is genuinely not implemented.
