"""Database engines and tenant-scoped sessions.

Two roles are used:

* ``DATABASE_MIGRATION_URL`` — privileged role for Alembic and seeding only.
* ``DATABASE_APP_URL`` — restricted runtime role. It is NOT a superuser and does
  not have ``BYPASSRLS``, so every query is additionally filtered by the
  Row-Level Security policy using a transaction-local organization setting.

``set_config(..., is_local => true)`` is used instead of a session-level ``SET``
so the tenant context can never leak through a pooled connection.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

_ENGINE_CACHE: dict[str, Engine] = {}


def _make_engine(url: str) -> Engine:
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_pool_size,
        pool_recycle=1800,
        echo=settings.database_echo,
        future=True,
    )


def get_app_engine() -> Engine:
    if "app" not in _ENGINE_CACHE:
        if not settings.database_app_url:
            raise RuntimeError("DATABASE_APP_URL is not configured")
        _ENGINE_CACHE["app"] = _make_engine(settings.database_app_url)
    return _ENGINE_CACHE["app"]


def get_privileged_engine() -> Engine:
    if "privileged" not in _ENGINE_CACHE:
        url = settings.database_migration_url or settings.database_app_url
        if not url:
            raise RuntimeError("DATABASE_MIGRATION_URL is not configured")
        _ENGINE_CACHE["privileged"] = _make_engine(url)
    return _ENGINE_CACHE["privileged"]


def app_session_factory() -> sessionmaker[Session]:
    return sessionmaker(
        bind=get_app_engine(), expire_on_commit=False, autoflush=False, future=True
    )


def privileged_session_factory() -> sessionmaker[Session]:
    return sessionmaker(
        bind=get_privileged_engine(), expire_on_commit=False, autoflush=False, future=True
    )


def dispose_engines() -> None:
    for engine in _ENGINE_CACHE.values():
        engine.dispose()
    _ENGINE_CACHE.clear()


def apply_tenant_context(session: Session, organization_id: uuid.UUID | str) -> None:
    """Set the transaction-local tenant used by the RLS policies."""
    session.execute(
        text("SELECT set_config('app.current_organization_id', :org, true)"),
        {"org": str(organization_id)},
    )


@contextmanager
def tenant_session(organization_id: uuid.UUID) -> Iterator[Session]:
    """Session bound to one tenant, committed on success."""
    session = app_session_factory()()
    try:
        session.begin()
        apply_tenant_context(session, organization_id)
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def privileged_session() -> Iterator[Session]:
    """Privileged session (migrations, seeding, identity lookup at login)."""
    session = privileged_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
