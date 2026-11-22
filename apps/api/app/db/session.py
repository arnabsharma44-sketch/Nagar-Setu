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
from app.db.urls import (
    connect_args_for,
    strip_driver_params,
    validate_database_url,
)

_ENGINE_CACHE: dict[str, Engine] = {}


def _make_engine(url: str) -> Engine:
    # ``normalize_database_url`` accepts Supabase's plain ``postgresql://`` URIs;
    # ``connect_args_for`` adds TLS and disables named prepared statements behind
    # the transaction-mode pooler. Local containers keep working unchanged.
    validate_database_url(url, ssl_mode=settings.database_ssl_mode)
    return create_engine(
        # ``strip_driver_params`` removes Prisma/Supabase hints such as
        # ``?pgbouncer=true`` that libpq would reject as an unknown option.
        strip_driver_params(url),
        pool_pre_ping=True,
        connect_args=connect_args_for(
            url,
            ssl_mode=settings.database_ssl_mode,
            connect_timeout=settings.database_connect_timeout_seconds,
        ),
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
