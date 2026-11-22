"""Database integration tests."""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


class TestDatabaseSchema:
    def test_all_tables_exist(self, db_engine: Engine) -> None:
        inspector = inspect(db_engine)
        tables = inspector.get_table_names()

        expected_tables = {
            "organizations", "users", "departments", "refresh_sessions",
            "contractors", "assets", "contracts", "contract_assets",
            "cameras", "videos", "ai_jobs", "detections", "evidence",
            "live_stream_sessions", "incidents", "accident_records",
            "investigations", "recommendations", "work_orders",
            "work_order_status_history", "verifications", "audit_logs",
            "hotspot_analyses",
        }
        assert expected_tables.issubset(set(tables)), f"Missing tables: {expected_tables - set(tables)}"

    def test_foreign_keys_exist(self, db_engine: Engine) -> None:
        inspector = inspect(db_engine)
        for table_name in inspector.get_table_names():
            fks = inspector.get_foreign_keys(table_name)
            for fk in fks:
                assert fk["referred_table"] in inspector.get_table_names()

    def test_composite_foreign_keys(self, db_engine: Engine) -> None:
        inspector = inspect(db_engine)
        fks = inspector.get_foreign_keys("users")
        fk_columns = [fk for fk in fks if "department_id" in fk["constrained_columns"]]
        assert len(fk_columns) >= 1
        fk = fk_columns[0]
        assert "organization_id" in fk["referred_columns"]

    def test_unique_constraints(self, db_engine: Engine) -> None:
        inspector = inspect(db_engine)
        for table in ["organizations", "users", "cameras", "assets", "contracts"]:
            if table in inspector.get_table_names():
                indexes = inspector.get_indexes(table)
                unique_indexes = [idx for idx in indexes if idx.get("unique")]
                assert len(unique_indexes) > 0, f"No unique constraints on {table}"

    def test_postgis_extension_available(self, db_engine: Engine) -> None:
        with db_engine.connect() as conn:
            result = conn.execute(text("SELECT PostGIS_Version()")).scalar()
            assert result is not None

    def test_rls_policies_exist(self, db_engine: Engine) -> None:
        with db_engine.connect() as conn:
            result = conn.execute(text("""
                SELECT tablename FROM pg_policies
                WHERE schemaname = 'public'
            """)).fetchall()
            tables_with_rls = {row[0] for row in result}
            tenant_tables = {
                "users", "departments", "contractors", "assets", "contracts",
                "contract_assets", "cameras", "videos", "ai_jobs", "detections",
                "evidence", "live_stream_sessions", "incidents", "accident_records",
                "investigations", "recommendations", "work_orders",
                "work_order_status_history", "verifications", "audit_logs",
                "hotspot_analyses",
            }
            assert tenant_tables.issubset(tables_with_rls)

    def test_rls_uses_transaction_local_setting(self, db_engine: Engine) -> None:
        with db_engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT polname, pg_get_expr(polqual, polrelid) AS using_expression
                    FROM pg_policy
                    WHERE polname = 'tenant_isolation'
                    """
                )
            ).fetchall()
        assert rows, "tenant_isolation policies must exist"
        for name, using_expression in rows:
            assert name == "tenant_isolation"
            assert using_expression, "every tenant policy needs a USING expression"
            assert "app.current_organization_id" in using_expression