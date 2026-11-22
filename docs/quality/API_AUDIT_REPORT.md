# API Audit Report

## Surface

- **82 operations across 69 paths**, derived from the live `app.openapi()` document.
- Matrix with per-operation access level: `docs/ENDPOINT_AUDIT.md`.
- Coverage test: `tests/integration/test_endpoint_coverage.py`.

The test is not a hand-written checklist. It walks operations in dependency order (registry →
camera → video → job → incident → accident import → hotspot → investigation → recommendation →
work order → completion → verification → audit → WebSocket), asserts the expected status for
each, forbids any 5xx, then diffs the invoked operation set against `app.openapi()`. A newly
documented endpoint that nobody calls fails the test; so does an undocumented call.

Result: **PASS**. 157 tests collected, full suite exit 0.

## Authentication and authorisation

| Probe | Result |
| --- | --- |
| Anonymous sweep of every operation | Only `/health/live`, `/health/ready`, `/meta/permissions`, `/auth/csrf`, `/auth/logout` answer 2xx; all others 401 |
| Same-origin / CSRF enforcement on mutations | Missing `x-csrf-token` rejected (covered by suite) |
| Auditor `GET /users` | 403 `PERMISSION_DENIED` |
| Auditor valid `POST /departments` | 403, `departments` count unchanged 14 → 14 |
| Engineer `GET /users` / `GET /audit-logs` | 403 |
| Engineer `GET /work-orders` | 200 |
| Auditor `GET /incidents` | 200 (read allowed) |
| Duplicate login emails across orgs | None (0 rows); the ambiguity path exists and returns `ORGANIZATION_REQUIRED` |

### Finding B-003

An unauthorised caller sending a **schema-invalid** body receives `422 VALIDATION_ERROR`
before the RBAC check produces `403`. No state changes and no data is returned, but the
validation message is disclosed to a role that may not perform the action. Severity P3;
fixing it means authorising before body validation, which changes the error contract, so it is
recorded rather than silently altered.

## Status contract observed

| Case | Response |
| --- | --- |
| Change password / logout | 204 |
| Unsupported media on upload | 415 `UNSUPPORTED_MEDIA_TYPE` |
| Oversized upload | 413 `PAYLOAD_TOO_LARGE` |
| Non-retryable job retry | 409 `JOB_NOT_RETRYABLE` |
| Wrong password | 401 `INVALID_CREDENTIALS` (generic, no user enumeration) |
| Disabled account | 401 `ACCOUNT_DISABLED` (after password verification) |
| Role denial | 403 `PERMISSION_DENIED` |
| Validation | 422 with field/reason details |

## Measured latency

Authenticated session as `ops@demo.roadguard.ai`, 23 parameterless GET operations, one pass,
local Docker network:

```
median 5 ms | p95 7 ms | max 9 ms
9 ms  200  35190 B  /api/v1/incidents
7 ms  200   7054 B  /api/v1/contracts
7 ms  200    545 B  /api/v1/incidents/analytics
6 ms  200  33232 B  /api/v1/investigations
```

Two non-2xx in that sweep are correct contract behaviour, not failures:
`/users` → 403 for the operations role, `/assets/nearby` → 422 because latitude/longitude are
required query parameters.

## Not verified

- Rate limiting: no limiter was exercised; no claim is made that one exists.
- Pagination, sorting and filter edge cases beyond the suite's parameters.
- Concurrency/duplicate-submit behaviour under parallel load.
- WebSocket behaviour during disconnect/reconnect.
