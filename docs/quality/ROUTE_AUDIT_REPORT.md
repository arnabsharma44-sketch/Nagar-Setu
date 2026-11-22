# Route Audit Report

Source of truth: filesystem inventory of `apps/web/app/**/page.tsx`, cross-checked against the
routes printed by `npm run build`. There are **23 pages**, not 21; 3 are dynamic.

Build result: `✓ Compiled successfully`, TypeScript finished, 21 static pages generated,
3 dynamic (`ƒ`) routes, proxy middleware present. `BUILD_EXIT=0`.

## Inventory and status

Legend: **PASS-browser** = opened in Chromium this audit; **PASS-build** = compiled and
server-rendered/prerendered but not individually opened; all pages below inherit the
middleware session gate.

| Route | Type | Auth | Render | Browser | Notes |
| --- | --- | --- | --- | --- | --- |
| `/` | static | public → redirect | PASS-build | — | Entry redirect |
| `/login` | static | public | PASS | PASS-browser | Labels present; demo accounts fill email only |
| `/command` | static | session | PASS | PASS-browser | Real metrics, map, realtime badge, job/event tables |
| `/command/cameras` | static | session | PASS-build | — | Registry table |
| `/command/monitoring` | static | session | PASS-build | — | Simulated-live controls |
| `/command/videos` | static | session | PASS-build | — | Upload + job progress |
| `/command/incidents` | static | session | PASS-build | — | Review queue |
| `/command/incidents/[id]` | dynamic | session | PASS-build | — | Event review |
| `/command/hotspots` | static | session | PASS-build | — | Map + methodology |
| `/command/investigations` | static | session | PASS-build | — | List |
| `/command/investigations/[id]` | dynamic | session | PASS-build | — | Analysis + recommendation |
| `/admin` | static | session | PASS | PASS-browser | 13 departments / 16 assets / 12 contracts |
| `/admin/departments` | static | session | PASS-build | — | CRUD table |
| `/admin/contractors` | static | session | PASS-build | — | CRUD table |
| `/admin/assets` | static | session | PASS-build | — | Registry + data-quality gaps |
| `/admin/contracts` | static | session | PASS-build | — | Contract ↔ asset links |
| `/admin/investigations` | static | session | PASS-build | — | Assignment |
| `/admin/investigations/[id]` | dynamic | session | PASS-build | — | Case view |
| `/admin/work-orders` | static | session | PASS-build | — | Pipeline table |
| `/admin/work-orders/[id]` | dynamic | session | PASS | PASS-browser | Direct cold load; 5-state timeline, evidence, verification |
| `/admin/analytics` | static | session | PASS-build | — | Aggregates |
| `/admin/audit-logs` | static | session | PASS-build | — | Read-only trail |
| `/admin/users` | static | session | PASS-build | — | Roles; 403 for non-admin API |

## Direct-access and refresh

- `/admin/work-orders/c2018a98-…` was opened directly (not via client navigation) and rendered
  the full record: title, department, priority, due date, completion notes, evidence with
  signed link, status history Pending→Assigned→In Progress→Completed Pending Verification→
  Verified, verification record, and "No transitions available from this state for your role."
- `/admin` and `/command` loaded cold after sign-in through middleware refresh.

## Console and network

- `/login`: two 401s on cold load (`/auth/me`, `/meta/bootstrap`) followed by `POST /auth/refresh`
  200 and `/meta/bootstrap` 200. This is the session-bootstrap sequence, not an error state.
- `/command`: all `_rsc` prefetches 200, OSM tiles 200, no errors after navigation.
- `/admin`: eight API calls 200 (`departments`, `assets`, `contractors`, `investigations`,
  `contracts`, `work-orders`, `audit-logs`, `incidents/analytics`), no errors.

## Not covered

Per-control interaction (every button/form/modal) and the 4-viewport matrix were not automated;
only the pages marked PASS-browser were opened. See `UI_CONTROL_INVENTORY.md` and
`VISUAL_REGRESSION_REPORT.md` for the precise gap.
