# Security, Privacy and Responsible AI Requirements

**Version:** 1.0  
**Status:** Mandatory implementation baseline

## 1. Security objective

Protect user identities, organization data, CCTV credentials, source videos, evidence files, contractor/asset records and administrative decisions. Prevent cross-organization disclosure and unauthorized camera access. Preserve a traceable record of consequential human actions.

## 2. Threat model

| Threat | Example | Required mitigation |
|---|---|---|
| Broken tenant isolation | User changes record UUID and reads another city's incident | Tenant-scoped queries, composite FKs, RLS, negative tests |
| Broken object-level authorization | User downloads another organization's video | Authorize every playback/download request; short-lived signed URL |
| Credential disclosure | RTSP password appears in JSON/logs | Secret references, server-side retrieval, redacted logs |
| SSRF via stream URL | User enters internal metadata-service URL as camera source | No arbitrary client URL; host allowlist, private-network controls, egress rules |
| Malicious upload | Crafted file exploits decoder or consumes resources | File validation, sandboxed worker, size/duration limits, patched FFmpeg |
| Token theft/CSRF | Cookie session abused from another origin | Secure/HttpOnly/SameSite cookies, CSRF protection, TLS, rotation |
| Privilege escalation | Client edits role or department ID | Server-derived permissions, protected admin routes |
| Evidence tampering | Edited clip presented as original evidence | Original object preservation, hashes, source/time metadata, audit trail |
| Prompt injection | Text embedded in uploaded documents instructs LLM to expose data | Treat records as untrusted data, fixed system instructions, no tool/SQL access |
| False attribution | AI blames contractor/officer | No automated liability; evidence-linked hypotheses and human review |
| Realtime leakage | WebSocket joins another tenant channel | Authenticate socket; derive organization server-side |
| Sensitive data over-retention | Raw surveillance video retained indefinitely | Configurable retention, deletion/hold controls, access logs |

## 3. Authentication

- Use a reputable password hashing algorithm supported by the selected framework (Argon2id preferred; bcrypt acceptable with appropriate parameters if required by library constraints).
- Never store plaintext passwords or reversible password encryption.
- Use rate limiting and generic login failure messages.
- Use short-lived access tokens and refresh-token rotation/revocation, or a secure server-side session system.
- Store refresh tokens as hashes if persisted.
- Cookies carrying credentials must be `Secure`, `HttpOnly` and appropriately `SameSite` in deployed environments.
- Add CSRF protection for cookie-authenticated state-changing requests.
- Support session revocation and account deactivation.

## 4. Authorization and tenant separation

- Use permission checks on every backend route and service method.
- Combine role permissions with organization and department/assignment scope.
- The authenticated principal determines organization ID; never trust a tenant ID supplied by the browser.
- Use tenant-aware composite foreign keys and PostgreSQL RLS as defence in depth.
- Use separate database roles for migrations and application runtime.
- Ensure RLS tenant context is transaction-local and cleared automatically.
- Apply the same tenant scope to REST, WebSocket, object storage, exports, search and background jobs.
- Celery jobs must carry a trusted tenant ID from the created database job record, not from arbitrary user payload fields.

## 5. Video and object storage security

- Store objects in private buckets with no public-read policy.
- Generate short-lived, narrowly scoped signed URLs after backend authorization.
- Validate filename, media type, signature/container, size and duration.
- Generate internal storage keys; do not trust user-supplied paths.
- Prevent path traversal and archive/decompression abuse.
- Process untrusted video in a constrained worker/container with limited permissions and resource quotas.
- Encrypt storage and transport where deployment supports it.
- Keep original source media immutable to normal users; store derived/annotated media as separate objects.
- Verify SHA-256 checksum when feasible and store it with evidence metadata.

## 6. RTSP and network controls

- Only authorized, registered cameras can be connected.
- RTSP endpoints are configured by a trusted administrator through a secure configuration path.
- Enforce camera host/network allowlists and block arbitrary public/internal destinations.
- Restrict worker egress to approved camera networks and required storage/API services.
- Store credentials in a secret manager or encrypted secret store; database stores only a reference.
- Redact connection strings from exceptions and logs.
- Provide a kill switch to disable all live camera ingestion.
- Never provide direct browser access to raw RTSP.

## 7. Privacy and data minimization

- Use synthetic video/data for public hackathon demonstrations wherever possible.
- Do not add facial recognition, identity recognition or number-plate recognition to the MVP.
- Avoid persisting person-level identity or stable tracking identifiers across jobs.
- Blur faces/plates in exported demonstration evidence when visible and practical; do not claim blurring is perfect.
- Limit access to raw footage to authorized roles and record access where appropriate.
- Define a configurable retention schedule for originals, clips, frames and derived analytics.
- Provide deletion/retention-hold behaviour subject to approved policy.
- Conduct a separate legal/privacy review before any real government or public deployment.

## 8. Evidence integrity and auditability

- Store source video reference, timestamp offsets, processing version, event-rule version and SHA-256 checksum.
- Record uploader and processing job identity.
- Maintain append-only application audit records for consequential actions.
- Record both successful and rejected review decisions.
- Do not overwrite previous AI processing results; reprocessing creates a new version/job.
- Do not imply that a file hash proves the original footage is authentic; it only helps detect changes after hashing.

## 9. Responsible AI requirements

- Display AI results as candidates until reviewed.
- Separate observations from hypotheses and decisions.
- Show known limitations and missing inputs.
- No automated legal, disciplinary or contractual-liability decisions.
- No automatic penalties or official notices.
- Human approval required for recommendations becoming work orders.
- Human verification required for work-order closure.
- LLM responses must be schema-validated and grounded in supplied records.
- If the LLM or detector is unavailable, manual workflow remains usable.
- Store model/rule version and input references to support review.

## 10. Minimum security tests before demo

1. User from Organization A cannot list/read/update Organization B records by guessing UUIDs.
2. User from Organization A cannot download Organization B video/evidence.
3. User with viewer role cannot create/assign/verify a work order.
4. Department user cannot access unassigned department cases unless policy permits.
5. WebSocket from Organization A never receives Organization B events.
6. Malformed/oversized/unsupported video is rejected safely.
7. Camera secrets do not appear in API response, UI, logs or error messages.
8. Audit entries cannot be modified/deleted through application routes.
9. A worker job cannot write an incident into a different tenant.
10. A user cannot mark their own completion as independently verified where separation of duties is configured.

## 11. Security response for prototype

Provide an admin-only mechanism to disable live ingestion and revoke sessions. Document known security limitations. Do not use the prototype with real public camera footage or official records until an appropriate security assessment and authorization are complete.
