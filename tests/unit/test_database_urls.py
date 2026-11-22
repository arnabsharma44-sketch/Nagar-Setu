"""Unit tests for database URL normalisation (local Postgres and Supabase)."""

from __future__ import annotations

import pytest
from app.db.urls import (
    connect_args_for,
    dsn_for_psycopg,
    ensure_direct_for_migrations,
    is_supabase_url,
    is_transaction_pooler,
    normalize_database_url,
    redact_database_url,
    strip_driver_params,
    validate_database_url,
)


def test_plain_supabase_url_gets_sqlalchemy_driver() -> None:
    url = "postgresql://postgres:pw@db.abcdefg.supabase.co:5432/postgres"
    assert normalize_database_url(url).startswith("postgresql+psycopg://")
    assert is_supabase_url(url)


def test_postgres_alias_is_normalised() -> None:
    url = "postgres://postgres:pw@db.abcdefg.supabase.co:5432/postgres"
    assert normalize_database_url(url) == (
        "postgresql+psycopg://postgres:pw@db.abcdefg.supabase.co:5432/postgres"
    )


def test_existing_driver_url_is_left_alone() -> None:
    url = "postgresql+psycopg://user:pw@localhost:5432/roadguard"
    assert normalize_database_url(url) == url
    assert not is_supabase_url(url)


def test_psycopg_dsn_strips_sqlalchemy_driver() -> None:
    assert dsn_for_psycopg("postgresql+psycopg://u:p@h:5432/db") == "postgresql://u:p@h:5432/db"
    assert dsn_for_psycopg("postgresql://u:p@h/db") == "postgresql://u:p@h/db"


def test_pooler_is_detected_and_disables_prepared_statements() -> None:
    url = "postgresql://u:p@aws-0-ap-south-1.pooler.supabase.com:6543/postgres"
    assert is_transaction_pooler(url)
    args = connect_args_for(url, ssl_mode="require")
    assert args["prepare_threshold"] is None
    assert args["sslmode"] == "require"


def test_direct_connection_keeps_prepared_statements() -> None:
    url = "postgresql://u:p@db.x.supabase.co:5432/postgres"
    args = connect_args_for(url, ssl_mode="require")
    assert "prepare_threshold" not in args
    assert args["sslmode"] == "require"
    assert not is_transaction_pooler(url)


def test_explicit_sslmode_in_url_wins() -> None:
    url = "postgresql://u:p@db.x.supabase.co:5432/postgres?sslmode=verify-full"
    assert "sslmode" not in connect_args_for(url, ssl_mode="require")


def test_local_url_keeps_prefer_and_has_no_pooler_flag() -> None:
    url = "postgresql+psycopg://roadguard_app:pw@postgres:5432/roadguard"
    args = connect_args_for(url)
    assert args["sslmode"] == "prefer"
    assert "prepare_threshold" not in args


def test_redaction_removes_password() -> None:
    assert redact_database_url("postgresql://postgres:secret@db.x.supabase.co:5432/postgres") == (
        "postgresql://postgres:***@db.x.supabase.co:5432/postgres"
    )


def test_empty_url_is_rejected() -> None:
    with pytest.raises(ValueError):
        normalize_database_url("   ")


def test_pgbouncer_query_flag_is_stripped_but_still_detected() -> None:
    url = (
        "postgresql://roadguard_app:pw@aws-0-ap-south-1.pooler.supabase.com:6543/postgres"
        "?pgbouncer=true&sslmode=require"
    )
    assert is_transaction_pooler(url)
    cleaned = strip_driver_params(url)
    assert "pgbouncer" not in cleaned
    assert "sslmode=require" in cleaned
    assert cleaned.startswith("postgresql+psycopg://")
    assert connect_args_for(url, ssl_mode="require")["prepare_threshold"] is None


def test_url_without_query_still_gets_the_driver() -> None:
    assert strip_driver_params("postgresql://u:p@h:5432/db") == (
        "postgresql+psycopg://u:p@h:5432/db"
    )


def test_supabase_without_tls_is_refused() -> None:
    url = "postgresql://postgres:pw@db.x.supabase.co:5432/postgres?sslmode=disable"
    with pytest.raises(ValueError, match="requires sslmode=require"):
        validate_database_url(url, ssl_mode="disable")


def test_pooler_without_tls_is_refused() -> None:
    url = "postgresql://u:p@h:6543/postgres"
    with pytest.raises(ValueError, match="requires sslmode=require"):
        validate_database_url(url, ssl_mode="allow")


def test_pgbouncer_flag_on_direct_port_is_refused() -> None:
    url = "postgresql://u:p@db.x.supabase.co:5432/postgres?pgbouncer=true&sslmode=require"
    with pytest.raises(ValueError, match="non-pooler URL"):
        validate_database_url(url, ssl_mode="require")


def test_migrations_refuse_the_transaction_pooler() -> None:
    with pytest.raises(ValueError, match="direct/session connection"):
        ensure_direct_for_migrations(
            "postgresql://postgres:pw@aws-0-ap.pooler.supabase.com:6543/postgres"
        )
    ensure_direct_for_migrations(
        "postgresql://postgres:pw@db.x.supabase.co:5432/postgres"
    )


def test_valid_combinations_pass_validation() -> None:
    validate_database_url(
        "postgresql://u:p@db.x.supabase.co:5432/postgres?sslmode=require", ssl_mode="prefer"
    )
    validate_database_url(
        "postgresql://u:p@h:6543/postgres?sslmode=require&pgbouncer=true", ssl_mode="prefer"
    )
    validate_database_url(
        "postgresql+psycopg://roadguard_app:pw@postgres:5432/roadguard", ssl_mode="prefer"
    )
