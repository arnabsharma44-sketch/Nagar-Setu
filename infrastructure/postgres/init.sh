#!/bin/bash
# PostgreSQL/PostGIS bootstrap for ROADGUARD AI.
#
# Runs once on first container start. Creates:
#   * pgcrypto + postgis extensions
#   * a restricted application role (subject to Row-Level Security)
# The role is intentionally NOT a superuser and has NO BYPASSRLS, so tenant
# isolation policies apply to every runtime query.
set -euo pipefail

APP_USER="${POSTGRES_APP_USER:-roadguard_app}"
APP_PASSWORD="${POSTGRES_APP_PASSWORD:?POSTGRES_APP_PASSWORD must be set}"
DB="${POSTGRES_DB:-roadguard}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$DB" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS pgcrypto;
    CREATE EXTENSION IF NOT EXISTS postgis;

    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '${APP_USER}') THEN
            CREATE ROLE ${APP_USER} LOGIN PASSWORD '${APP_PASSWORD}';
        ELSE
            ALTER ROLE ${APP_USER} WITH LOGIN PASSWORD '${APP_PASSWORD}';
        END IF;
    END
    \$\$;

    ALTER ROLE ${APP_USER} NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;

    GRANT CONNECT ON DATABASE ${DB} TO ${APP_USER};
    GRANT USAGE ON SCHEMA public TO ${APP_USER};
    ALTER DEFAULT PRIVILEGES IN SCHEMA public
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ${APP_USER};
    ALTER DEFAULT PRIVILEGES IN SCHEMA public
        GRANT USAGE, SELECT ON SEQUENCES TO ${APP_USER};
    GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO ${APP_USER};
    ALTER DEFAULT PRIVILEGES IN SCHEMA public
        GRANT EXECUTE ON FUNCTIONS TO ${APP_USER};
EOSQL

echo "ROADGUARD AI: database extensions and restricted application role are ready."
