# Bug Register

| ID | Severity | Status | Summary |
| --- | --- | --- | --- |
| B-001 | P3 | FIXED | Dataset helper printed the archive stem instead of the dataset key in follow-up commands |
| B-002 | P2 | FIXED | Dashboard "Cameras online" counted enabled cameras, reporting 13/13 when 0 were online |
| B-003 | P3 | OPEN | Schema validation (422) precedes RBAC denial (403) on some writes |
| B-005 | P2 | FIXED | "Latest events" claimed N candidates need review, computed from the page slice, contradicting the dashboard total |
| B-004 | P3 | OBSERVATION | One transient `INVALID_CREDENTIALS` for a valid password, not reproducible |
| S-01 | P3 local / P2 public | OPEN | No CSP or HSTS header (nosniff/frame-deny/referrer present) |
| S-02 | P2 deployment | BLOCKED | Secure/SameSite cookie flags unverifiable on plain-HTTP local stack |
| S-03 | P3 | OPEN | No login rate limiting observed |

## B-001 — wrong dataset key in manual instructions

- **Reproduce:** `python scripts/datasets/download_datasets.py --dataset all`. The printed
  "Then:" line said `verify_downloads.py --dataset AICity21-Track4-Anomaly-Detection`.
- **Cause:** `manual_instructions()` derived the key from `archive_name.split(".")[0]`.
- **Fix:** key is passed in explicitly (`manual_instructions(entry, name)`).
- **Verify:** re-run prints `--dataset aicity2021_track4` / `rdd2022_india` / `bdd100k`;
  `verify_downloads.py --dataset all` then resolves all three entries.

## B-002 — misleading camera metric

- **Reproduce:** open `/command`. Card read "Cameras online 13/13" while the map legend listed
  cameras as `offline`. Database: 11 offline, 2 unknown, 0 online.
- **Cause:** `apps/web/app/command/page.tsx` counted `camera.is_enabled` and labelled it "online";
  the hint even said "Registered camera registry entries".
- **Fix:** count `camera.connection_status === "online"`, hint now "Reporting online in the
  registry, not merely enabled".
- **Verify:** TypeScript build passes; with current data the card reports `0/13`, matching SQL.
  This matters beyond cosmetics: claiming cameras are online when they are not is exactly the
  kind of unsupported operational claim the project forbids.

## B-005 — review-count contradiction

- **Reproduce:** open `/command`. Metric card "AI candidate events" showed 2 while the events
  card said "0 candidate event(s) still need a review decision".
- **Cause:** the description counted `review_status === "pending"` inside the latest-events page
  slice instead of the organisation total returned by `/incidents/analytics`.
- **Fix:** the description now uses `analytics.data.pending_candidates`; the slice-local counter
  was removed.
- **Verify:** rebuild; card and description agree at 2 with current data.

## B-003 — validation before authorisation

- **Reproduce:** as `auditor`, `POST /api/v1/departments` with a body missing
  `department_type` → `422` with field details. With a valid body → `403`.
- **Cause:** request-body validation runs before the role dependency resolves.
- **Impact:** no state change, no data read; discloses validation rules to a role that cannot
  act. Low severity.
- **Fix (not applied):** authorise before body validation. This changes the error contract for
  unauthorised callers, so it is left as a documented decision rather than silently altered.

## B-004 — unreproduced 401

- **Observation:** at 10:41:56 a direct `POST /auth/login` with the documented password returned
  401 `INVALID_CREDENTIALS`; the container log confirms the API handled it.
- **Follow-up:** six consecutive logins immediately afterwards (ops and reviewer) returned 200,
  and `audit_logs` shows successful `auth.login` one minute earlier. No lockout columns exist on
  `users` and the auth path has no lockout branch.
- **Status:** not reproducible; recorded rather than dismissed. If it recurs, capture the
  `request_id` and the exact request body.

## Non-bugs confirmed during the audit

- `/api/v1/users` → 403 for the operations role: correct RBAC.
- `/api/v1/assets/nearby` → 422 without coordinates: required parameters.
- Two 401s on the login page cold load: session bootstrap (`/auth/me` before refresh).
- "Cameras offline" rows belong to the second organisation's audit fixtures and are displayed
  only within their own tenant.
