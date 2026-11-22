# End-to-End Test Report

## Principal integration test (no mocks)

Command:

```bash
.venv/Scripts/python.exe scripts/demo_smoke.py --external-worker
```

This drives the real HTTP API and the real worker container against the real PostgreSQL and
storage. Exit code 0. Output, verbatim excerpts:

```
2/12 upload synthetic CCTV clip
    video=1c518368-9117-41c9-97ad-8c6eceae027d status=processing
3/12 background processing
    job=312c3194-… queued; the polling worker processes it asynchronously
    model=synthetic-scene-colour-marker v=synthetic_scene_v1 rules=1.0.0 events=1
4/12 candidate events
    type=near_miss_candidate score=0.436 window=3.0-9.0s
5/12 evidence artefacts
    evidence=2 items, annotated frame 63211 bytes
6/12 reviewer confirms the candidate event
    review_status=confirmed
7/12 open an investigation on the nearby asset
    case=INV-2026-0024
8/12 asset/department/contract record match
    status=matched_records department=Audit Public Works cb901931 contracts=['CT-cb901931']
9/12 draft investigation analysis
    source=deterministic hypotheses=1 missing=1
10/12 draft recommendation and independent approval
    self-approval blocked, independent approval recorded
11/12 work order, completion evidence and channel separation
    work order=WO-2026-0024 status=pending
12/12 independent verification and audit trail
    audit entries=100 verified
OK: full workflow completed end to end.
```

Assertions inside the script check persisted state at each step, not just response codes:
review status, case number, matched department/contract, self-approval rejection, work-order
status, verified flag and audit count.

## Browser flow

Driven in Chromium against the production web container:

1. `/login` — labelled form, DEMO notice, demo accounts.
2. Typed email + password, submitted with Enter → authenticated session.
3. `/command` — 2 pending, 26 confirmed, 19 historical, camera card `0/14` (after the B-002 fix), map with OSM tiles,
   realtime "Connected (ticket-authenticated)", recent jobs and latest events tables.
4. `/admin` — 13 departments, 16 assets, 12 contracts, 2 open work orders, data-quality list,
   recent audited actions.
5. `/admin/work-orders/{id}` opened **directly** — full detail, evidence, five-state timeline,
   verification record, separation-of-duties = Enforced.

Network: every API call returned 200; no console error after navigation.

## What this does not prove

- The browser pass followed /command → /admin → detail; it did not re-run the full 12-step
  workflow through the UI (upload form, review buttons, work-order transitions). The API-level
  run covers those transitions; the UI wiring for each is unverified.
- No Playwright script exists in the repo, so none of this is repeatable in CI yet.
