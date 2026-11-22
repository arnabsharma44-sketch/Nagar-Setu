"""Alembic environment for ROADGUARD AI.

Migrations run with the privileged database role. The runtime API uses a
restricted role that is subject to Row-Level Security.
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

API_DIR = Path(__file__).resolve().parents[1]
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

import app.models  # noqa: E402,F401  (registers all tables)
from app.core.config import settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.urls import (  # noqa: E402
    ensure_direct_for_migrations,
    strip_driver_params,
    validate_database_url,
)  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

database_url = settings.database_migration_url or settings.database_app_url
if not database_url:
    raise RuntimeError("DATABASE_MIGRATION_URL must be set to run migrations")
# Alembic interpolates this value through configparser, so a literal % in a
# generated password must be escaped or the connection URL is mangled.
ensure_direct_for_migrations(database_url)
validate_database_url(database_url, ssl_mode=settings.database_ssl_mode)
config.set_main_option(
    "sqlalchemy.url",
    strip_driver_params(database_url).replace("%", "%%"),
)
# Migrations read this to target grants/revokes without hard-coding a role name.
config.set_main_option("roadguard_app_role", settings.postgres_app_user)

target_metadata = Base.metadata

POSTGIS_MANAGED_TABLES = {
    "spatial_ref_sys",
    "geography_columns",
    "geometry_columns",
    "raster_columns",
    "raster_overviews",
    "topology_layer",
}


def include_object(object_, name, type_, reflected, compare_to):  # noqa: ANN001, ARG001
    """Ignore PostGIS/tiger helper objects that live in the same search path."""
    if type_ == "table" and name in POSTGIS_MANAGED_TABLES:
        return False
    if reflected and name not in Base.metadata.tables and type_ in {"table", "index"}:
        return False
    if reflected and type_ == "table":
        return name in Base.metadata.tables
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
