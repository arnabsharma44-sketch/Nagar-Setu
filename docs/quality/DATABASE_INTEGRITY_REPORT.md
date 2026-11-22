# Database Integrity Report

Target: `roadguard-postgres` (PostgreSQL 16 + PostGIS), database `roadguard`, role `roadguard`.

## Structure

| Check | Result |
| --- | --- |
| Alembic head | `837c7ef69730 (head)` |
| Base tables in `public` | 25 (incl. `spatial_ref_sys`) |
| Tables with RLS enabled | 23 |
| RLS policies | 23 |
| Tables with RLS but no policy | 0 |
| Foreign keys | 60 |
| Unvalidated FKs / CHECKs | 0 / 0 |
| Composite FK definitions duplicated | 0 |
| Tables with an index containing `organization_id` | 22 |
| PostGIS geometry | Geometry columns present (Tiger geocoder tables installed in `public`) |

RLS is not assumed: `tests/integration/test_database.py` asserts the policy expression
contains `app.current_organization_id`, and the runtime role is
`roadguard_app` (`NOSUPERUSER NOBYPASSRLS NOINHERIT`) so policies actually apply. The migration
role is separate; using Supabase's `postgres` at runtime would silently bypass RLS.

## Data present

```
organizations 2 | users 17 | cameras 14 | videos 43 | ai_jobs 28
detections 3009 | incidents 27 | investigations 24 | recommendations 24
work_orders 24 | verifications 22 | audit_logs 1593
```

## Integrity sweep (all expected 0)

| Check | Result |
| --- | --- |
| Incident → video (same org) | 0 |
| Incident → camera (same org) | 0 |
| Detection → job (same org) | 0 |
| Evidence with no parent | 0 |
| Evidence incident org mismatch | 0 |
| Work order → investigation (same org) | 0 |
| Investigation incident org mismatch | 0 |
| Video camera org mismatch | 0 |
| Duplicate incident per (job, type) | 0 |

## Immutability of the audit trail

Executed as the runtime role inside a rolled-back transaction:

```
begin; set local role roadguard_app;
update audit_logs set action='tampered';   -- ERROR: permission denied for table audit_logs
delete from audit_logs;                    -- ERROR: permission denied for table audit_logs
rollback;
```

`UPDATE` and `DELETE` are denied at the grant level, not merely by convention. Application code
has append-only access.

## Transactions

Background jobs use `SELECT … FOR UPDATE SKIP LOCKED` style leasing with an attempt counter and
lease expiry; the polling runner and the Celery worker both go through that path. The
end-to-end run completed 12/12 steps with 100 audit entries and no partial records, and the
orphan sweep above found no half-written relationships.

## Not verified

- Behaviour under a killed worker mid-job (lease recovery is unit-covered, not fault-injected).
- Physical backup/restore (no backup configured on the local stack).
- Query plans for datasets far larger than the demo volume.
