"""Append-only audit helper."""

from __future__ import annotations

import uuid
from typing import Any

from app.models import AuditLog
from sqlalchemy.orm import Session


def record_audit(
    session: Session,
    *,
    organization_id: uuid.UUID,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
    actor_label: str | None = None,
    request_id: str | None = None,
    summary: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditLog:
    """Write one audit row inside the caller's transaction.

    There is deliberately no update/delete helper: the database blocks both for
    the runtime role.
    """
    entry = AuditLog(
        organization_id=organization_id,
        actor_id=actor_id,
        actor_label=actor_label,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        request_id=request_id,
        summary=summary,
        metadata_json=metadata or {},
    )
    session.add(entry)
    session.flush()
    return entry
