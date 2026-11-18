# Database and Data Model Specification

**Version:** 1.0  
**Database:** PostgreSQL + PostGIS  
**Status:** Prototype baseline

## 1. Database principles

- PostgreSQL is the source of truth for business records.
- Every tenant-owned row carries `organization_id`.
- Tenant-scoped uniqueness and relationships must be enforced in the database, not only in Python.
- Use UUID primary keys for application entities.
- Persist times as `TIMESTAMPTZ` in UTC.
- Store geospatial points as `GEOGRAPHY(POINT, 4326)` when measuring earth-surface distance; use `GEOMETRY` with a suitable projected SRID for planar operations where justified.
- Store file bytes in private object storage and only store `storage_key`, checksum, MIME type and metadata in PostgreSQL.
- Never store passwords or stream credentials in plaintext.
- Maintain provenance for imported records and AI-generated observations.

## 2. Entity catalogue

| Entity | Purpose | Tenant-owned |
|---|---|---|
| organizations | Tenant/city/agency boundary | Root |
| users | Named human identities | Yes |
| departments | Organization departments | Yes |
| user_department_memberships (optional) | Multiple department assignments | Yes |
| contractors | Registered contractors | Yes |
| assets | Roads, intersections, signals, lights, crossings and other assets | Yes |
| contracts | Contract scope, period and associated contractor/asset/department | Yes |
| cameras | Camera metadata and registered location | Yes |
| videos | Uploaded or captured video metadata | Yes |
| ai_jobs | Asynchronous processing state/configuration | Yes |
| detections (optional detail table) | Frame/object tracking output where needed | Yes |
| incidents | Potential or reviewed events detected/entered by users | Yes |
| accident_records | Imported historical accident records | Yes |
| evidence | Evidence metadata and storage references | Yes |
| investigations | Human-governed cases and findings | Yes |
| recommendations | Draft/approved/rejected proposed interventions | Yes |
| work_orders | Department corrective actions | Yes |
| work_order_status_history | Work-order transition history | Yes |
| verifications | Independent completion checks | Yes |
| audit_logs | Append-only security/business audit events | Yes |

## 3. Relationships

- Organization has many users, departments, assets, cameras, videos, incidents and work orders.
- Department maintains or owns many assets and receives many work orders.
- Contractor has many contracts; a contract may cover an asset or defined group/scope of assets.
- Camera has many videos and may be associated with many incidents.
- Video has many AI jobs if reprocessed with distinct model/rule versions; each job can generate many detections/events.
- Incident may link to one source video/camera, many evidence items and one or more investigations.
- Investigation may link to an incident and one or more assets; it has many findings/recommendations/work orders.
- Work order has status history and one or more verification attempts.
- User actions are recorded in audit logs.

## 4. Core columns and constraints

### organizations

`id UUID PK`, `name`, `organization_type`, `city`, `state`, `created_at`.

### users

`id UUID PK`, `organization_id FK`, `department_id nullable FK`, `full_name`, `email`, `password_hash`, `is_active`, `created_at`, `updated_at`.

Constraint: `UNIQUE(organization_id, normalized_email)`. Email must be normalized before persistence. A global identity provider may instead use a globally unique subject ID; do not silently merge separate identities by display name.

### departments

`id UUID PK`, `organization_id FK`, `name`, `department_type`, `contact_email`, timestamps.

Constraint: `UNIQUE(organization_id, normalized_name)` where appropriate.

### assets

`id UUID PK`, `organization_id FK`, `department_id nullable`, `asset_code`, `name`, `asset_type`, `address`, `location GEOGRAPHY(POINT,4326) nullable`, `condition_status`, `source_reference`, `last_inspected_at`, timestamps.

Constraint: `UNIQUE(organization_id, asset_code)`. Department relationship must be tenant-aware.

### contractors

`id UUID PK`, `organization_id FK`, `name`, `registration_number`, `contact_email`, `source_reference`, timestamps.

### contracts

`id UUID PK`, `organization_id FK`, `contractor_id`, `department_id`, `contract_number`, `contract_type`, `scope_description`, `start_date`, `end_date`, `warranty_end_date`, `source_reference`, timestamps.

Use a join table such as `contract_assets(contract_id, asset_id, organization_id, scope_notes)` for contracts covering multiple assets. Avoid assuming every contract maps to exactly one asset.

### cameras

`id UUID PK`, `organization_id FK`, `camera_code`, `name`, `location nullable`, `source_type`, `secret_reference nullable`, `connection_status`, `is_enabled`, `last_seen_at`, timestamps.

Constraint: `UNIQUE(organization_id, camera_code)`. The secret reference points to a secret manager/config entry; the actual RTSP password is never stored in a user-readable field.

### videos

`id UUID PK`, `organization_id FK`, `camera_id nullable`, `uploaded_by`, `storage_key`, `original_filename`, `content_type`, `file_size_bytes`, `checksum_sha256`, `source_type` (`upload`, `rtsp_recording`, `demo_replay`), `recorded_at nullable`, `duration_seconds nullable`, `status`, `retention_expires_at nullable`, timestamps.

### ai_jobs

`id UUID PK`, `organization_id FK`, `video_id FK`, `job_type`, `status`, `progress`, `idempotency_key`, `model_name`, `model_version`, `weights_sha256`, `event_rules_version`, `config_snapshot JSONB`, `started_at`, `completed_at`, `error_code`, `error_message_safe`, timestamps.

Constraint: `UNIQUE(organization_id, idempotency_key)` for deduplication.

### incidents

`id UUID PK`, `organization_id FK`, `camera_id nullable`, `video_id nullable`, `ai_job_id nullable`, `incident_type`, `source_kind` (`ai_candidate`, `manual_observation`, `imported`), `severity nullable`, `model_score nullable`, `event_time`, `start_offset_seconds nullable`, `end_offset_seconds nullable`, `location nullable`, `description`, `review_status`, `reviewed_by nullable`, `reviewed_at nullable`, `review_notes nullable`, `created_at`.

Use `model_score` rather than `confidence` when the score is not a calibrated probability. The API can display “model score” or “detection score”. Never imply a 0.91 model score means a 91% chance that an accident occurred.

### accident_records

`id UUID PK`, `organization_id FK`, `external_reference nullable`, `location nullable`, `accident_time nullable`, `accident_type nullable`, `severity nullable`, `source_name`, `source_reference`, `verification_status`, `import_batch_id nullable`, `created_at`.

Historical records must be visibly distinct from AI candidate incidents. Record provenance and import date.

### evidence

`id UUID PK`, `organization_id FK`, `incident_id nullable`, `investigation_id nullable`, `work_order_id nullable`, `storage_key`, `evidence_type`, `timestamp_in_video nullable`, `content_type`, `file_size_bytes`, `checksum_sha256`, `created_by`, `created_at`.

At least one parent reference is required; enforce valid parent/tenant relationships. Evidence access must be authorized on every retrieval.

### investigations

`id UUID PK`, `organization_id FK`, `case_number`, `incident_id nullable`, `asset_id nullable`, `assigned_department_id nullable`, `assigned_to nullable`, `title`, `observed_facts JSONB`, `hypotheses JSONB`, `missing_information JSONB`, `status`, `opened_by`, `closed_by nullable`, timestamps.

Constraint: `UNIQUE(organization_id, case_number)`.

Keep facts, hypotheses and administrative decisions in separate fields or normalized tables. Never write AI hypotheses into the verified-facts field.

### recommendations

`id UUID PK`, `organization_id FK`, `investigation_id FK`, `recommendation_text`, `rationale`, `priority`, `status` (`draft`, `approved`, `rejected`, `superseded`), `model_name nullable`, `model_version nullable`, `input_snapshot JSONB`, `created_by`, `reviewed_by nullable`, `reviewed_at nullable`, timestamps.

### work_orders

`id UUID PK`, `organization_id FK`, `investigation_id FK`, `recommendation_id nullable`, `assigned_department_id FK`, `assigned_to nullable`, `title`, `description`, `status`, `priority`, `due_date nullable`, `completed_at nullable`, `created_by`, timestamps.

### work_order_status_history

`id UUID PK`, `organization_id FK`, `work_order_id FK`, `from_status nullable`, `to_status`, `changed_by`, `note nullable`, `created_at`.

### verifications

`id UUID PK`, `organization_id FK`, `work_order_id FK`, `verified_by`, `verification_status` (`accepted`, `rejected`, `needs_more_evidence`), `notes`, `verified_at`, `created_at`.

The verifier should be distinct from the completion submitter where policy requires separation of duties.

### audit_logs

`id UUID PK`, `organization_id FK`, `actor_id nullable`, `action`, `entity_type`, `entity_id`, `request_id nullable`, `metadata JSONB`, `created_at`.

Normal application users must not have UPDATE or DELETE permission on audit records. For stronger tamper evidence, export/chain records to an external append-only system in a future deployment.

## 5. Tenant isolation requirements

Every tenant-owned table must include `organization_id`. For every relationship between tenant-owned rows, enforce that both parent and child have the same organization.

Recommended approach:

1. Add `UNIQUE(id, organization_id)` to parent tables.
2. Add composite foreign keys such as `(department_id, organization_id) REFERENCES departments(id, organization_id)`.
3. Use PostgreSQL RLS policies with transaction-scoped tenant context as defence in depth.
4. Set tenant context using a transaction-local setting (for example `SET LOCAL app.current_organization_id = ...`) and ensure it is reset automatically at transaction end.
5. Use a restricted runtime database role; migrations use a separate privileged role.
6. Test with two organizations and attempt direct-ID, list, search, download and WebSocket cross-tenant access.

Do not use a connection-wide tenant setting that can leak between pooled requests. Do not let the frontend set the authoritative tenant ID.

## 6. Indexes

Minimum indexes:

- Tenant filter: `(organization_id, created_at DESC)` on high-volume tables.
- Incidents: `(organization_id, event_time DESC)`, `(organization_id, review_status)`.
- Jobs: `(organization_id, status, created_at)`.
- Work orders: `(organization_id, status, due_date)`.
- Assets/cameras/incidents: GiST index on geographic column.
- Asset lookup: `(organization_id, asset_code)` unique.
- Camera lookup: `(organization_id, camera_code)` unique.
- Video jobs: unique idempotency key per organization.

## 7. Hotspot query and calculation notes

- Use PostGIS distance/proximity queries with an explicit radius and coordinate source.
- Keep separate aggregates for (a) verified historical accidents, (b) human-confirmed camera observations, (c) unreviewed AI candidates and (d) near-miss candidates.
- Do not label a cluster “accident blackspot” based only on AI detections.
- If traffic exposure data is available, compute rates with documented numerator/denominator and time window. Otherwise label the map as “incident/event concentration”, not normalized risk.
- Store the calculation method, parameter values, data window and generated timestamp with each hotspot result.

## 8. Migration and seed-data rules

- Every schema change uses an Alembic migration.
- Migrations must be reversible where practical and must never silently drop user data.
- Seed script must be idempotent and create fictional demo records only.
- Prefix demo codes with `DEMO-` and show a demo-data banner in the UI.
- Never use actual personal, vehicle-registration or police data in seed files.

## 9. Data retention and deletion

Define configurable retention periods for raw videos, derived clips, frames, job outputs and audit records. Deletion must check legal/administrative holds and preserve required audit metadata. The hackathon prototype may use a simple configurable retention field and explicit admin-only delete workflow; it must not claim to meet a jurisdiction's statutory retention requirements without review.
