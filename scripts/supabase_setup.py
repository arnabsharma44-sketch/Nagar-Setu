"""Provision and verify ROADGUARD AI's database on Supabase (or any managed PostGIS).

Supabase hands out a single privileged connection string. This project still wants
two roles: a privileged one for Alembic/seed and an unprivileged one that is
subject to Row-Level Security at runtime. This script closes that gap:

    python scripts/supabase_setup.py --url "postgresql://postgres:...@db.<ref>.supabase.co:5432/postgres"

With no action flag it only inspects the database. Add ``--bootstrap`` to create the
extensions and the restricted role, ``--write-env`` to persist the connection
strings in ``.env`` for the API/containers, and ``--migrate`` to run Alembic.

The password is never printed; only a redacted URL is echoed.
"""

from __future__ import annotations

import argparse
import os
import secrets
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "apps" / "api"
for candidate in (API_DIR, ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from app.core.config import settings  # noqa: E402
from app.db.urls import (  # noqa: E402
    dsn_for_psycopg,
    host_of,
    is_transaction_pooler,
    redact_database_url,
    strip_driver_params,
)

DEFAULT_APP_USER = "roadguard_app"


def connect(url: str, *, timeout: int = 20) -> psycopg.Connection:
    # Supabase's copy-paste strings may carry ?pgbouncer=true, which libpq rejects.
    return psycopg.connect(
        dsn_for_psycopg(strip_driver_params(url)), autocommit=True, connect_timeout=timeout
    )


def scalar(conn: psycopg.Connection, query: str, params: tuple | None = None):
    with conn.cursor() as cur:
        cur.execute(query, params)
        row = cur.fetchone()
        return row[0] if row else None


def inspect(
    conn: psycopg.Connection, app_user: str, *, host: str = ""
) -> list[tuple[str, str, bool]]:
    """Return (label, value, ok) rows without ever showing credentials."""
    server = scalar(conn, "show server_version")
    user = scalar(conn, "select current_user")
    database = conn.info.dbname
    ssl_in_use = scalar(
        conn,
        "select coalesce((select ssl from pg_stat_ssl where pid = pg_backend_pid()), false)",
    )
    postgis = scalar(
        conn,
        "select extversion from pg_extension where extname = 'postgis'",
    )
    postgis_schema = scalar(
        conn,
        """
        select n.nspname from pg_extension e
        join pg_namespace n on n.oid = e.extnamespace
        where e.extname = 'postgis'
        """,
    )
    pgcrypto = scalar(conn, "select extversion from pg_extension where extname = 'pgcrypto'")
    rls_tables = scalar(
        conn,
        """
        select count(*) from pg_class c
        join pg_namespace n on n.oid = c.relnamespace
        where n.nspname = 'public' and c.relkind = 'r' and c.relrowsecurity
        """,
    )
    app_row = None
    with conn.cursor() as cur:
        cur.execute(
            """
            select rolsuper, rolbypassrls, rolcanlogin from pg_roles where rolname = %s
            """,
            (app_user,),
        )
        app_row = cur.fetchone()
    policy_count = scalar(
        conn,
        "select count(*) from pg_policies where schemaname = 'public'",
    )
    # TLS is mandatory for a managed database; a loopback development database is
    # the one case where an unencrypted session is expected.
    loopback = host in {"localhost", "127.0.0.1", "::1", "postgres", ""}
    rows = [
        ("server version", str(server), True),
        ("database", str(database), True),
        ("connected as", str(user), True),
        (
            "TLS on this session",
            "yes" if ssl_in_use else ("no (loopback)" if loopback else "no"),
            bool(ssl_in_use) or loopback,
        ),
        ("PostGIS", str(postgis) if postgis else "MISSING", bool(postgis)),
        ("PostGIS schema", str(postgis_schema or "-"), True),
        ("pgcrypto", str(pgcrypto) if pgcrypto else "MISSING", bool(pgcrypto)),
        ("RLS-enabled tables", str(rls_tables), True),
        ("RLS policies", str(policy_count), True),
    ]
    if app_row is None:
        rows.append((f"role {app_user}", "MISSING (RLS will not be enforced)", False))
    else:
        rolsuper, rolbypassrls, rolcanlogin = app_row
        detail = (
            f"login={'yes' if rolcanlogin else 'no'} "
            f"superuser={'yes' if rolsuper else 'no'} "
            f"bypassrls={'yes' if rolbypassrls else 'no'}"
        )
        rows.append((f"role {app_user}", detail, rolcanlogin and not rolsuper and not rolbypassrls))
    return rows


def bootstrap(conn: psycopg.Connection, app_user: str, app_password: str | None) -> list[str]:
    """Create extensions, the restricted role and its grants. Idempotent.

    ``app_password=None`` means "leave the existing password alone". That is what
    makes a re-run safe behind a connection pooler: rotating the password without
    telling pgbouncer first leaves it retrying a dead credential and every client
    then waits out ``server_login_retry``.
    """
    database = conn.info.dbname
    actions: list[str] = []
    extensions_schema = scalar(
        conn, "select 1 from pg_namespace where nspname = 'extensions'"
    )

    with conn.cursor() as cur:
        cur.execute("create extension if not exists pgcrypto")
        actions.append("extension pgcrypto ensured")
        if extensions_schema:
            cur.execute("create extension if not exists postgis with schema extensions")
        else:
            cur.execute("create extension if not exists postgis")
        actions.append("extension postgis ensured")

        exists = scalar(conn, "select 1 from pg_roles where rolname = %s", (app_user,))
        if not exists and app_password is None:
            raise RuntimeError(
                f"role {app_user} does not exist; pass --app-password (or let the "
                "script generate one) so it can be created"
            )
        if not exists:
            cur.execute(
                sql.SQL("create role {} login password {}").format(
                    sql.Identifier(app_user), sql.Literal(app_password)
                )
            )
            actions.append(f"role {app_user} created")
        # Always reset the security-relevant attributes: a role that once had
        # BYPASSRLS would silently defeat tenant isolation. The password is only
        # touched when one was supplied, so re-running cannot invalidate a pooler
        # that already holds the current credential.
        password_clause = (
            sql.SQL(" password {}").format(sql.Literal(app_password))
            if app_password is not None
            else sql.SQL("")
        )
        is_super = bool(
            scalar(conn, "select rolsuper from pg_roles where rolname = current_user")
        )
        super_clause = " nosuperuser" if is_super else ""
        cur.execute(
            sql.SQL(
                "alter role {} with login{}"
                + super_clause
                + " nobypassrls nocreatedb nocreaterole noinherit"
            ).format(sql.Identifier(app_user), password_clause)
        )
        actions.append(
            f"role {app_user} restricted "
            f"(no superuser, no bypassrls; password {'rotated' if app_password else 'unchanged'})"
        )

        search_path = 'public, extensions' if extensions_schema else "public"
        cur.execute(
            sql.SQL(
                'alter role {} in database {} set search_path to "$user", '
            ).format(sql.Identifier(app_user), sql.Identifier(database))
            + sql.SQL(search_path)
        )
        actions.append("search_path includes the PostGIS schema")

        cur.execute(
            sql.SQL("grant connect on database {} to {}").format(
                sql.Identifier(database), sql.Identifier(app_user)
            )
        )
        cur.execute(
            sql.SQL("grant usage on schema public to {}").format(sql.Identifier(app_user))
        )
        if extensions_schema:
            cur.execute(
                sql.SQL("grant usage on schema extensions to {}").format(
                    sql.Identifier(app_user)
                )
            )
        cur.execute(
            sql.SQL(
                "grant select, insert, update, delete on all tables in schema public to {}"
            ).format(sql.Identifier(app_user))
        )
        cur.execute(
            sql.SQL(
                "grant usage, select on all sequences in schema public to {}"
            ).format(sql.Identifier(app_user))
        )
        cur.execute(
            sql.SQL(
                "grant execute on all functions in schema public to {}"
            ).format(sql.Identifier(app_user))
        )
        cur.execute(
            sql.SQL(
                "alter default privileges in schema public "
                "grant select, insert, update, delete on tables to {}"
            ).format(sql.Identifier(app_user))
        )
        cur.execute(
            sql.SQL(
                "alter default privileges in schema public "
                "grant usage, select on sequences to {}"
            ).format(sql.Identifier(app_user))
        )
        cur.execute(
            sql.SQL(
                "alter default privileges in schema public grant execute on functions to {}"
            ).format(sql.Identifier(app_user))
        )
        actions.append("grants applied to current and future objects")

        # Re-running the bootstrap after migrations must not restore DML on the
        # append-only audit table.
        if scalar(conn, "select to_regclass('public.audit_logs')") is not None:
            cur.execute(
                sql.SQL("revoke update, delete on public.audit_logs from {}").format(
                    sql.Identifier(app_user)
                )
            )
            actions.append("audit_logs DML re-revoked (append-only preserved)")
    return actions


def _with_credentials(url: str, user: str, password: str) -> str:
    parts = urlsplit(url)
    netloc = parts.netloc
    host = parts.hostname or ""
    port = f":{parts.port}" if parts.port else ""
    host_part = f"[{host}]" if ":" in host else host
    netloc = f"{quote(user, safe='')}:{quote(password, safe='')}@{host_part}{port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def upsert_env(path: Path, values: dict[str, str]) -> list[str]:
    """Replace keys in .env without printing or reordering unrelated entries."""
    existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    pending = dict(values)
    out: list[str] = []
    for line in existing:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in pending:
                out.append(f"{key}='{pending.pop(key).replace(chr(39), chr(92) + chr(39))}'")
                continue
        out.append(line)
    if pending:
        if out and out[-1].strip():
            out.append("")
        out.append("# --- Supabase (written by scripts/supabase_setup.py) ---")
        for key, value in pending.items():
            out.append(f"{key}='{value.replace(chr(39), chr(92) + chr(39))}'")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return sorted(values)


def run_migrations(migration_url: str, app_url: str) -> int:
    env = dict(os.environ)
    env["DATABASE_MIGRATION_URL"] = migration_url
    env["DATABASE_APP_URL"] = app_url
    env["PYTHONPATH"] = str(API_DIR)
    print("\nRunning: alembic upgrade head (apps/api)")
    completed = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(API_DIR),
        env=env,
        check=False,
    )
    return completed.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--url",
        # .env is read by Settings, so the secret never has to appear in a shell
        # argument or in shell history.
        default=(
            os.environ.get("SUPABASE_DB_URL")
            or settings.supabase_db_url
            or os.environ.get("DATABASE_MIGRATION_URL")
        ),
        help=(
            "Privileged connection string (Supabase -> Connect). Defaults to SUPABASE_DB_URL "
            "from the environment or .env."
        ),
    )
    parser.add_argument(
        "--app-url",
        default=os.environ.get("SUPABASE_POOLER_URL") or settings.supabase_pooler_url or None,
    )
    parser.add_argument("--app-user", default=DEFAULT_APP_USER)
    parser.add_argument("--app-password", default=None)
    parser.add_argument("--bootstrap", action="store_true", help="Create extensions, role and grants.")
    parser.add_argument("--write-env", action="store_true", help="Persist the URLs in .env.")
    parser.add_argument("--migrate", action="store_true", help="Run alembic upgrade head.")
    parser.add_argument("--env-file", default=str(ROOT / ".env"))
    args = parser.parse_args(argv)

    if not args.url:
        parser.error("--url (or SUPABASE_DB_URL) is required")

    migration_url = args.url
    # None means "keep the existing password". Only generate one when the role has
    # to be created, or when the operator explicitly asks to rotate it.
    app_password: str | None = args.app_password
    print(f"Database: {redact_database_url(migration_url)}")
    if is_transaction_pooler(migration_url):
        if args.migrate:
            print(
                "error: --migrate requires the direct/session connection (port 5432). "
                "The transaction pooler cannot hold a migration transaction across "
                "statements. Re-run with the direct SUPABASE_DB_URL.",
                file=sys.stderr,
            )
            return 2
        print(
            "note: this URL uses the transaction pooler (6543); inspection/bootstrap "
            "are fine, but never run migrations through it."
        )

    try:
        with connect(migration_url) as conn:
            role_exists = scalar(
                conn, "select 1 from pg_roles where rolname = %s", (args.app_user,)
            )
            role_has_password = (
                bool(
                    scalar(
                        conn,
                        "select rolpassword is not null from pg_roles where rolname = %s",
                        (args.app_user,),
                    )
                )
                if role_exists
                else False
            )
            # Generate only when there is nothing usable to keep: a new role, or one
            # created without a password (the local init SQL does that deliberately).
            if app_password is None and not role_has_password:
                app_password = secrets.token_urlsafe(24)
            rows = inspect(conn, args.app_user, host=host_of(migration_url))
            width = max(len(label) for label, _, _ in rows)
            for label, value, ok in rows:
                print(f"  [{'ok' if ok else '!!'}] {label.ljust(width)}  {value}")

            if args.bootstrap:
                actions = bootstrap(conn, args.app_user, app_password)
                print("\nBootstrap:")
                for action in actions:
                    print(f"  - {action}")
                rows = inspect(conn, args.app_user, host=host_of(migration_url))
    except Exception as exc:  # noqa: BLE001 - CLI surface
        print(f"\nFAILED to reach the database: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    failed = [label for label, _, ok in rows if not ok]
    if failed:
        print(
            "\nNot ready: " + ", ".join(failed) + ". Fix these before deploying the API.",
            file=sys.stderr,
        )
        return 1

    if args.bootstrap:
        app_url = args.app_url or (
            _with_credentials(migration_url, args.app_user, app_password)
            if app_password is not None
            else None
        )
        if app_url and not args.app_url:
            print(
                f"\nApp role connection (redacted): {redact_database_url(app_url)}"
            )
            print(
                "For containers/preview deployments use the Supabase pooler URL on port 6543 "
                "and pass it with --app-url; direct 5432 also works if your network allows it."
            )
        if app_url is None:
            print(
                "\nApp role password unchanged. Pass --app-url with the existing runtime URL, "
                "or --app-password to rotate it (then reload the connection pooler)."
            )
        if app_url and is_transaction_pooler(app_url):
            print("info: pooler detected — named prepared statements are disabled automatically.")
        if args.write_env and app_url is None:
            print(
                "error: --write-env needs the runtime URL; pass --app-url.",
                file=sys.stderr,
            )
            return 2
        if args.write_env:
            keys = upsert_env(
                Path(args.env_file),
                {
                    "SUPABASE_DB_URL": migration_url,
                    "DATABASE_MIGRATION_URL": migration_url,
                    "DATABASE_APP_URL": app_url,
                    "COMPOSE_DATABASE_MIGRATION_URL": migration_url,
                    "COMPOSE_DATABASE_APP_URL": app_url,
                    "DATABASE_SSL_MODE": "require",
                },
            )
            print(f"\n.env updated ({Path(args.env_file)}): {', '.join(keys)}")
        if args.migrate:
            return run_migrations(migration_url, app_url or migration_url)
        return 0

    if args.write_env or args.migrate:
        print(
            "\n--write-env/--migrate need --bootstrap so the restricted role exists.",
            file=sys.stderr,
        )
        return 2
    print("\nInspection complete. Re-run with --bootstrap --write-env --migrate to switch over.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
