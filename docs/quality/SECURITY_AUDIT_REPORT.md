# Security Audit Report

## Authentication

| Control | Result |
| --- | --- |
| Password hashing | Argon2id (`$argon2id$` rows in `users`) |
| Unknown-email handling | Dummy hash verification, identical 401 `INVALID_CREDENTIALS` — no user enumeration |
| Session model | Short-lived access cookie + rotating refresh session row (`refresh_sessions.token_hash`) |
| Refresh reuse | Reuse revokes all sessions for the account and writes `auth.refresh_reuse_detected` |
| CSRF | Mutations require `x-csrf-token` matching the CSRF cookie |
| Role selection at login | Not offered in the UI and not accepted as a client-authoritative field |

## Authorisation

Role checks are server-side and independent of the UI.

```
auditor   GET /users             403 PERMISSION_DENIED
engineer  GET /users             403
engineer  GET /audit-logs        403
auditor   POST /departments      403 (valid body), departments 14 -> 14
auditor   GET /incidents         200
```

Tenant scoping: every query is executed on a session that sets `app.current_organization_id`,
with RLS enforced by the non-bypassing runtime role. Cross-tenant probes in
`tests/integration/test_tenant_isolation.py` and the integrity sweep in
`DATABASE_INTEGRITY_REPORT.md` found no cross-organisation rows.

## Storage and evidence

- Uploads use signed, short-lived tokens; evidence download and "exists" checks are token-scoped
  and covered by the endpoint suite.
- Evidence rows carry `checksum_sha256` and are tied to an organisation.
- Generated demo frames are labelled synthetic in the UI.
- No public bucket path is exposed to the frontend.

## Secrets

- `.env` is not tracked (`git ls-files .env` → not a tracked path); `.env.example` holds names only.
- No `rtsp://` URL or credential appears in the web app sources.
- Camera rows store `secret_reference`, not a plaintext stream password.
- Supabase support reads the DSN from the environment; the setup script never prints the password
  and redacts URLs in diagnostics.

## Transport headers (measured)

Present on both tiers:

```
API  /api/v1/health/live : x-content-type-options: nosniff | x-frame-options: DENY |
                           referrer-policy: no-referrer | cache-control: no-store
WEB  /login              : x-content-type-options: nosniff | x-frame-options: DENY |
                           referrer-policy: no-referrer
```

Still absent: `Content-Security-Policy` and `Strict-Transport-Security`. HSTS only makes sense
behind TLS; CSP is worth adding before public exposure (the app loads OSM tiles and inline
Next.js styles, so a policy needs care). Recorded as **S-01, P3 local / P2 public**.

## Findings

| ID | Severity | Description |
| --- | --- | --- |
| B-003 | P3 | Schema validation runs before the RBAC denial, so an unauthorised caller gets `422` with field details instead of `403`. No state change. |
| S-01 | P3 local / P2 public | `nosniff`, `X-Frame-Options: DENY` and `Referrer-Policy` are present; CSP and HSTS are not. |
| S-02 | P2 (deployment) | Cookies must be `Secure` + `SameSite` behind TLS; the local stack runs plain HTTP, so this could not be verified. |
| S-03 | P3 | No login rate limiting observed in the auth path. |

## Not verified

- Penetration testing, dependency CVE scanning and TLS configuration.
- Object-storage policy review against a real S3/MinIO deployment.
- WebSocket authorisation under token replay (ticket single-use is implemented and unit-tested).
