"""Database URL handling for local PostgreSQL and managed Supabase.

Supabase hands out plain ``postgresql://`` URIs and requires TLS. SQLAlchemy needs
an explicit driver, and psycopg must not rely on named prepared statements when the
connection goes through Supabase's transaction-mode pooler (port 6543). Both
normalisations live here so the API, Alembic and the operational scripts agree
instead of each parsing the URL on its own.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

SQLALCHEMY_DRIVER = "postgresql+psycopg"
_PLAIN_PREFIXES = ("postgresql://", "postgres://")
_PASSWORD_RE = re.compile(r"(://[^:/@]+:)[^@]*(@)")


def normalize_database_url(url: str) -> str:
    """Return a SQLAlchemy URL with the psycopg driver spelled out."""
    if not url or not url.strip():
        raise ValueError("A database URL is required.")
    value = url.strip()
    if value.startswith("postgres://"):
        return SQLALCHEMY_DRIVER + "://" + value[len("postgres://") :]
    if value.startswith("postgresql://"):
        return SQLALCHEMY_DRIVER + "://" + value[len("postgresql://") :]
    return value


def dsn_for_psycopg(url: str) -> str:
    """Strip the SQLAlchemy driver suffix so libpq/psycopg can parse the URL."""
    value = url.strip()
    scheme, separator, rest = value.partition("://")
    if separator and "+psycopg" in scheme:
        return "postgresql://" + rest
    return value


# Query parameters that belong to a pooler (Prisma/Supabase style), not to libpq.
# libpq rejects unknown keywords outright: `invalid connection option "pgbouncer"`.
DRIVER_UNSUPPORTED_PARAMS = frozenset({"pgbouncer"})


def strip_driver_params(url: str) -> str:
    """Remove pooler hints that libpq/psycopg cannot parse.

    Supabase's copy-paste pooler strings often carry ``?pgbouncer=true``. The flag is
    meaningful to us (it selects unnamed prepared statements) but must never reach the
    driver, so it is read first and then dropped from the URL.
    """
    parts = _parts(url)
    if not parts.query:
        return normalize_database_url(url.strip())
    query = [
        (key, value)
        for key, values in parse_qs(parts.query, keep_blank_values=True).items()
        if key not in DRIVER_UNSUPPORTED_PARAMS
        for value in values
    ]
    cleaned = urlunsplit(parts._replace(query=urlencode(query)))
    return normalize_database_url(cleaned)


def ensure_direct_for_migrations(url: str) -> None:
    """Alembic needs a real session; transaction pooling cannot hold DDL safely.

    Supabase's pooler multiplexes statements across server connections, so a
    migration's implicit transaction (and its advisory locks, temp state and
    extension DDL) can land on different sessions. Refusing here is clearer than
    a half-applied schema.
    """
    if is_transaction_pooler(url):
        raise ValueError(
            "Migrations must use a direct/session connection on port 5432 (or the "
            "session pooler), not the transaction pooler on 6543. "
            "Use the direct SUPABASE_DB_URL for DATABASE_MIGRATION_URL and keep the "
            "pooler URL for DATABASE_APP_URL."
        )


def validate_database_url(url: str, *, ssl_mode: str = "prefer") -> None:
    """Fail clearly on combinations that would silently disable a guarantee.

    Two are refused outright:
    * TLS disabled against a Supabase host or the transaction pooler — managed
      Postgres will not accept it, and failing here is clearer than a timeout;
    * ``pgbouncer=true`` on the direct/session port, which claims transaction
      pooling where none exists and would disable prepared statements for nothing.
    """
    parts = _parts(url)
    query = parse_qs(parts.query)
    requested_ssl = (query.get("sslmode", [ssl_mode])[0] or "").lower()
    insecure = requested_ssl in {"disable", "allow"}
    managed = is_supabase_url(url) or is_transaction_pooler(url)
    if managed and insecure:
        raise ValueError(
            "Refusing to connect without TLS: Supabase (and its transaction pooler) "
            "requires sslmode=require or verify-full, got "
            f"sslmode={requested_ssl or 'unset'}. "
            "Put ?sslmode=require on the connection URL."
        )
    pooler_flag = query.get("pgbouncer", [""])[0].lower() in {"true", "1"}
    port = parts.port or 5432
    if pooler_flag and port != 6543:
        raise ValueError(
            "pgbouncer=true was set on a non-pooler URL (port "
            f"{port}). Use the transaction pooler port 6543 for the "
            "runtime URL, or remove ?pgbouncer=true for a direct connection."
        )


def _parts(url: str):
    return urlsplit(normalize_database_url(url))


def host_of(url: str) -> str:
    return (_parts(url).hostname or "").lower()


def is_supabase_url(url: str) -> bool:
    host = host_of(url)
    return host.endswith(".supabase.co") or host.endswith(".supabase.com")


def is_transaction_pooler(url: str) -> bool:
    """Supabase's pooler on port 6543 multiplexes statements across transactions."""
    parts = _parts(url)
    if parts.port == 6543:
        return True
    query = parse_qs(parts.query)
    return query.get("pgbouncer", [""])[0].lower() in {"true", "1"}


def connect_args_for(
    url: str, *, ssl_mode: str = "prefer", connect_timeout: int = 10
) -> dict[str, object]:
    """libpq/psycopg connection options implied by the URL and settings.

    * ``sslmode`` is only injected when the URL does not already specify TLS, so an
      explicit ``?sslmode=verify-full`` always wins.
    * A transaction-mode pooler cannot keep named prepared statements per session;
      psycopg is told to use unnamed statements instead of failing at runtime.
    """
    query = parse_qs(_parts(url).query)
    args: dict[str, object] = {}
    if ssl_mode and "sslmode" not in query and "ssl" not in query:
        args["sslmode"] = ssl_mode
    if connect_timeout and connect_timeout > 0 and "connect_timeout" not in query:
        args["connect_timeout"] = connect_timeout
    if is_transaction_pooler(url):
        args["prepare_threshold"] = None
    return args


def redact_database_url(url: str) -> str:
    """Same URL with the password replaced, safe for logs and CLI output."""
    return _PASSWORD_RE.sub(r"\1***\2", url.strip())


__all__ = [
    "DRIVER_UNSUPPORTED_PARAMS",
    "connect_args_for",
    "dsn_for_psycopg",
    "host_of",
    "is_supabase_url",
    "is_transaction_pooler",
    "normalize_database_url",
    "redact_database_url",
    "ensure_direct_for_migrations",
    "strip_driver_params",
    "validate_database_url",
]
