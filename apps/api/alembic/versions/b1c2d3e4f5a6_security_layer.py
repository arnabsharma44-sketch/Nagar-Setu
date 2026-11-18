"""Security layer: extensions, Row-Level Security, append-only audit, job claim.

Revision ID: b1c2d3e4f5a6
Revises: a0f8b507499d
Create Date: 2026-11-18

This migration adds defence-in-depth controls that cannot be expressed in the
SQLAlchemy models:

* Row-Level Security on every tenant-owned table, keyed on the transaction-local
  ``app.current_organization_id`` setting (never a session-level setting, so a
  pooled connection cannot leak a tenant).
* An append-only audit trail (privilege revocation plus a trigger).
* ``claim_ai_job``: a SECURITY DEFINER function used by the worker to atomically
  claim one queued job. It is the only sanctioned cross-tenant read, and it
  returns nothing but the job id and the organization id recorded on the job row.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b1c2d3e4f5a6"
down_revision = "a0f8b507499d"
branch_labels = None
depends_on = None

TENANT_TABLES = [
    "departments",
    "users",
    "refresh_sessions",
    "contractors",
    "assets",
    "contracts",
    "contract_assets",
    "cameras",
    "videos",
    "ai_jobs",
    "detections",
    "evidence",
    "live_stream_sessions",
    "incidents",
    "accident_records",
    "investigations",
    "recommendations",
    "work_orders",
    "work_order_status_history",
    "verifications",
    "audit_logs",
    "hotspot_analyses",
]


def upgrade() -> None:
    connection = op.get_bind()
    owner_role = connection.execute(sa.text("SELECT current_user")).scalar()
    app_role = op.get_context().config.get_main_option("roadguard_app_role") or "roadguard_app"

    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # --- Row-Level Security -------------------------------------------------
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {table}
            USING (organization_id = nullif(current_setting('app.current_organization_id', true), '')::uuid)
            WITH CHECK (organization_id = nullif(current_setting('app.current_organization_id', true), '')::uuid)
            """
        )

    op.execute("ALTER TABLE organizations ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON organizations
        USING (id = nullif(current_setting('app.current_organization_id', true), '')::uuid)
        WITH CHECK (id = nullif(current_setting('app.current_organization_id', true), '')::uuid)
        """
    )

    # --- Append-only audit trail -------------------------------------------
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION prevent_audit_log_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF current_user = '{owner_role}' THEN
                RETURN COALESCE(NEW, OLD);
            END IF;
            RAISE EXCEPTION 'audit_logs is append-only';
        END
        $$
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_audit_logs_append_only ON audit_logs")
    op.execute(
        """
        CREATE TRIGGER trg_audit_logs_append_only
        BEFORE UPDATE OR DELETE ON audit_logs
        FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_mutation()
        """
    )
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{app_role}') THEN
                EXECUTE format(
                    'REVOKE UPDATE, DELETE, TRUNCATE ON audit_logs FROM %I', '{app_role}'
                );
                EXECUTE format('GRANT SELECT, INSERT ON audit_logs TO %I', '{app_role}');
            END IF;
        END
        $$
        """
    )

    # --- Worker job claim ---------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION claim_ai_job(
            p_worker_id text,
            p_lease_seconds integer DEFAULT 900,
            p_max_attempts integer DEFAULT 3
        )
        RETURNS TABLE(out_job_id uuid, out_organization_id uuid)
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public
        AS $$
        DECLARE
            claimed ai_jobs;
        BEGIN
            SELECT j.* INTO claimed
            FROM ai_jobs j
            WHERE j.status = 'queued'
               OR (j.status = 'running' AND j.lease_expires_at IS NOT NULL AND j.lease_expires_at < now())
            ORDER BY j.created_at
            FOR UPDATE SKIP LOCKED
            LIMIT 1;

            IF claimed.id IS NULL THEN
                RETURN;
            END IF;

            UPDATE ai_jobs
               SET status = 'running',
                   stage = 'validating',
                   lease_owner = p_worker_id,
                   lease_expires_at = now() + make_interval(secs => p_lease_seconds),
                   started_at = COALESCE(started_at, now()),
                   attempts = attempts + 1,
                   updated_at = now()
             WHERE id = claimed.id;

            out_job_id := claimed.id;
            out_organization_id := claimed.organization_id;
            RETURN NEXT;
        END
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION claim_ai_job(text, integer, integer) FROM PUBLIC")
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{app_role}') THEN
                EXECUTE format(
                    'GRANT EXECUTE ON FUNCTION claim_ai_job(text, integer, integer) TO %I',
                    '{app_role}'
                );
            END IF;
        END
        $$
        """
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS claim_ai_job(text, integer, integer)")
    op.execute("DROP TRIGGER IF EXISTS trg_audit_logs_append_only ON audit_logs")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_log_mutation()")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON organizations")
    op.execute("ALTER TABLE organizations DISABLE ROW LEVEL SECURITY")
    for table in reversed(TENANT_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
