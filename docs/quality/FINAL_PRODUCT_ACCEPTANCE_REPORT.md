# Final Product Acceptance Report

## Criteria

| # | Criterion | Status | Basis |
| --- | --- | --- | --- |
| 1 | All frontend routes inspected | **PARTIAL** | 23 routes inventoried; 4 opened in a browser, 19 compile and prerender but were not individually opened |
| 2 | Interactive controls inventoried and tested | **PARTIAL** | Inventoried from rendered trees; navigation, login, direct detail load tested; admin forms not clicked |
| 3 | Principal forms work | **PASS** | Login; upload; investigation; recommendation; work order — all executed via API and reflected in UI |
| 4 | Both portals functional | **PASS** | Command and admin render live data with zero failed requests |
| 5 | Major APIs tested | **PASS** | 82/69 operations executed; OpenAPI diff gate; anonymous sweep |
| 6 | Authentication and RBAC | **PASS** | Login/refresh/logout; auditor/engineer denials 403; auditor write blocked, no row created |
| 7 | Multi-tenant isolation | **PASS** | 23/23 RLS + policies; tenant tests; zero cross-org rows in integrity sweep |
| 8 | Video upload and processing | **PASS** | Upload → queued job → worker → 100% → evidence |
| 9 | AI detection and tracking reproducible | **PASS (synthetic)** | Same clip produces the same candidate; tracker IDs persisted |
| 10 | Six event rules evaluated | **PASS (unit)** | Converging and decelerating scenarios assert expected events |
| 11 | GIS and hotspot consistency | **PASS** | GeoJSON 200; map and API counts agree; coordinates only from registered records |
| 12 | Department/contractor mapping | **PASS** | `matched_records` with department and contract id in the E2E run |
| 13 | Work orders and independent verification | **PASS** | Full lifecycle plus self-approval rejection and verifier record |
| 14 | Migrations and relationships valid | **PASS** | Head `837c7ef69730`; 60 FKs validated; zero orphans |
| 15 | WebSocket updates | **PARTIAL** | Ticket-authenticated connection established; broadcast delivery not asserted end to end |
| 16 | No known P0/P1 defects | **PASS** | None open; one P2 fixed (camera metric) |
| 17 | Dataset acquisition documented | **PASS** | All three sources probed, BLOCKED, exact manual steps recorded |
| 18 | Dataset formats validated | **PASS (tooling)** | Fixture pipeline validated all stages; real archives absent |
| 19 | Model performance claims backed by evaluation | **PASS (no claims)** | No real metric asserted anywhere; evaluator refuses without predictions |
| 20 | Full end-to-end workflow | **PASS** | 12/12 with 100 audit entries |

Score: 14 PASS, 1 PASS (synthetic), 2 PASS (tooling/no-claims), 3 PARTIAL, 0 FAIL.

## What actually works

- Two-portal product on real database content, honest DEMO labelling, and a complete
  incident → investigation → work order → independent verification → audit chain.
- Tenant isolation that is enforced at the database, not just in handlers.
- An AI pipeline whose outputs are candidates, with evidence and rule versions recorded.

## What does not work / is missing

- Real-world detection accuracy: **unknown and unmeasured**. No labelled data, no YOLO weights.
- Road-damage detection: **not implemented**.
- Live RTSP: no feed; simulated replay only, labelled as such.
- Automated UI/a11y/load testing: tooling absent.
- Supabase: credentials and endpoints configured in `.env`; bootstrap and schema ready for live deployment.

## Bugs fixed

1. **B-002** — the dashboard claimed cameras were online based on `is_enabled`; now uses real
   connection status.
2. **B-001** — dataset helper printed an unusable `--dataset` argument.

## Readiness verdict

**Ready for a hackathon demonstration on synthetic data — with the limitations stated out loud.**
Not ready for a pilot on real footage until: an authorised feed exists, a licensed detector is
installed and benchmarked on labelled data, CSP/HSTS and cookie flags are configured, and the
UI/a11y test gap is closed.

The one thing that would most improve the demo's credibility is AI City Track 4 labels driving a
real precision/recall number. The tooling to produce it is finished and waiting for the archive.
