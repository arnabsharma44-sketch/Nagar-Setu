"""The audit trail must be append-only for the application role.

This runs directly against PostgreSQL with the same credentials the API uses, so it
proves the database blocks tampering even if application code were bypassed.
"""

from __future__ import annotations

import pytest
from app.core.config import settings
from app.db.session import privileged_session
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError, ProgrammingError


def test_audit_rows_exist_to_test_against() -> None:
    with privileged_session() as session:
        count = session.execute(text("SELECT count(*) FROM audit_logs")).scalar_one()
    assert count > 0


def test_application_role_cannot_update_or_delete_audit_rows() -> None:
    from sqlalchemy import create_engine

    engine = create_engine(settings.database_app_url, future=True)
    with engine.connect() as connection, pytest.raises((ProgrammingError, DBAPIError, IntegrityError)):
        connection.execute(
            text("UPDATE audit_logs SET action = 'tampered.action' WHERE id IS NOT NULL")
        )
        connection.commit()

    with engine.connect() as connection, pytest.raises((ProgrammingError, DBAPIError, IntegrityError)):
        connection.execute(text("DELETE FROM audit_logs WHERE id IS NOT NULL"))
        connection.commit()
    engine.dispose()


def test_audit_rows_are_still_readable_after_the_attempt(login_as, client) -> None:
    login_as("ops@demo.roadguard.ai")
    response = client.get("/api/v1/audit-logs?limit=5")
    assert response.status_code == 200
    entries = response.json()["data"]
    assert entries
    assert all(entry["action"] != "tampered.action" for entry in entries)
